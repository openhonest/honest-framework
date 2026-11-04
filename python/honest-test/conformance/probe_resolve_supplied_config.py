"""Conformance fragment for the resolve_supplied_config scenario (honest-test.feature).

Scenario: resolve_supplied_config builds the supplied-values record from the
  decoded table.
  Then it returns a SuppliedConfig, a map from predicate name to that predicate's
  SuppliedEntry — its valid list, its invalid list and its strategy.
  And it reads the decoded table as data, builds the record the generators take,
  and touches no world.
  And a predicate absent from the table yields the missing-entry warning rather
  than a file lookup (so a table declaring no predicates resolves to {}).

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.resolve_supplied_config on a plain parsed-TOML table (a map
of maps, what tomllib produces) and compares the returned dict by value.

Input-schema gap: the .hd note for resolve_supplied_config names sections 3.6 and
10 for the TOML layout but does not reproduce the section/key names. These rows
assume the direct map-of-maps layout the note describes — each predicate name maps
to a table carrying "valid", "invalid" and "strategy". If the fixed schema nests
predicates under a section or renames the keys, these inputs need updating; the
output shape and the empty-table result are fixed by the note.

This is its own fragment file so the other scenarios' fragments never collide with
it. The shared conformance runner and laws files are untouched.
"""

from honest_test import resolve_supplied_config

_CASES = [
    # (a) one predicate carrying valid + invalid + strategy. All three fields of
    # the SuppliedEntry are non-trivial, so a stub returning {} cannot pass.
    {
        "given": {
            "table": {
                "is_fizz": {
                    "valid": ["fizz", "buzz"],
                    "invalid": ["baz"],
                    "strategy": "supplied_only",
                }
            }
        },
        "expect": {
            "is_fizz": {
                "valid": ["fizz", "buzz"],
                "invalid": ["baz"],
                "strategy": "supplied_only",
            }
        },
    },
    # (b) two predicates, one per strategy. The record carries both entries, each
    # with its own valid/invalid lists.
    {
        "given": {
            "table": {
                "is_small": {
                    "valid": ["1", "2"],
                    "invalid": ["999"],
                    "strategy": "fibonacci",
                },
                "is_name": {
                    "valid": ["ann"],
                    "invalid": ["x", "y"],
                    "strategy": "supplied_only",
                },
            }
        },
        "expect": {
            "is_small": {
                "valid": ["1", "2"],
                "invalid": ["999"],
                "strategy": "fibonacci",
            },
            "is_name": {
                "valid": ["ann"],
                "invalid": ["x", "y"],
                "strategy": "supplied_only",
            },
        },
    },
    # (d) the fibonacci strategy exercised on its own, with empty invalid, so the
    # strategy field is pinned independently of the supplied_only rows.
    {
        "given": {
            "table": {
                "is_number": {
                    "valid": ["0", "1", "1", "2", "3"],
                    "invalid": [],
                    "strategy": "fibonacci",
                }
            }
        },
        "expect": {
            "is_number": {
                "valid": ["0", "1", "1", "2", "3"],
                "invalid": [],
                "strategy": "fibonacci",
            }
        },
    },
    # (c) the explicit absence case: a table declaring no predicates resolves to
    # the empty SuppliedConfig. Required, never the only case.
    {
        "given": {"table": {}},
        "expect": {},
    },
]


def probe_resolve_supplied_config():
    """resolve_supplied_config reshapes the decoded table into a SuppliedConfig keyed by predicate name, each entry carrying its valid list, invalid list and strategy, and the empty map when no predicate is declared."""
    bad = []
    for case in _CASES:
        got = resolve_supplied_config(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"resolve_supplied_config({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_resolve_supplied_config()
    for line in bad:
        print(line)
    print(f"probe_resolve_supplied_config: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
