"""Conformance fragment for the mutate_source scenario (honest-test.feature).

Scenario: mutate_source generates every mechanical mutant of a module's source,
  or a Fault when it does not parse.
  Then it parses the source with tree-sitter and applies each of the seven change
  kinds to every place it fits, returning one Mutant per change — a swapped
  comparison, a shifted number, a flipped condition, a replaced constant, a
  swapped result, a removed line, a changed membership or key — each carrying its
  node span and the original and replacement text.
  And it returns a Fault when the source does not parse, because a mutant can only
  be made from parseable source.

Cases are data; one pure probe feeds them to the real honest_test.mutate_source
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: it calls the real function on Python source strings.

The exact node span and the exact replacement text depend on tree-sitter, so this
probe asserts on the change_kind set each snippet must produce, on one literal
`<` -> `<=` comparison swap, and on the Fault-vs-list distinction — never on spans.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import mutate_source

# A pin names one Mutant the snippet must contain: a change_kind, a substring the
# original must hold, a substring the replacement must hold, and that the two differ.
# The comparison-swap pin fixes a literal, non-trivial output (`<` -> `<=`), so a
# stub returning [] cannot pass.
_CASES = [
    # (a) A comparison operator and a number literal. Applicable kinds include the
    # comparison swap and the number shift; the swap is pinned to `<` -> `<=`.
    {
        "name": "comparison and number",
        "source": "def f(n):\n    return n < 5\n",
        "is_fault": False,
        "must_contain_kinds": {"comparison_swap", "number_shift"},
        "pins": [
            {
                "change_kind": "comparison_swap",
                "original_has": "<",
                "replacement_has": "<=",
            }
        ],
    },
    # (a2) The `<=` operator, the other direction of the comparison-swap table. Its
    # swap is pinned to `<=` -> `<`, so the `<=` KEY of the swap table is exercised,
    # not only the `<` key case (a) covers.
    {
        "name": "less-equal comparison",
        "source": "def f(n):\n    return n <= 5\n",
        "is_fault": False,
        "must_contain_kinds": {"comparison_swap", "number_shift"},
        "pins": [
            {
                "change_kind": "comparison_swap",
                "original_has": "<=",
                "replacement_has": "<",
            }
        ],
    },
    # (b1) A bare number literal yields a number shift.
    {
        "name": "number literal",
        "source": "def g():\n    return 5\n",
        "is_fault": False,
        "must_contain_kinds": {"number_shift"},
        "pins": [
            {
                "change_kind": "number_shift",
                "original_has": "5",
                "replacement_has": "",
            }
        ],
    },
    # (b2) A boolean `and` yields a condition flip, pinned to `and` -> `or`.
    {
        "name": "boolean and",
        "source": "def h(a, b):\n    return a and b\n",
        "is_fault": False,
        "must_contain_kinds": {"condition_flip"},
        "pins": [
            {
                "change_kind": "condition_flip",
                "original_has": "and",
                "replacement_has": "or",
            }
        ],
    },
    # (c) The absence / fault path: source that does not parse as Python. The return
    # is the Fault dict {problem, remedy}, never a list of mutants.
    {
        "name": "unparseable source",
        "source": "def f( : return\n",
        "is_fault": True,
        "must_contain_kinds": set(),
        "pins": [],
    },
]


def _pin_satisfied(mutants, pin):
    """True when some mutant matches the pin's kind and holds its original/replacement text."""
    for m in mutants:
        if (
            m.get("change_kind") == pin["change_kind"]
            and pin["original_has"] in m.get("original", "")
            and pin["replacement_has"] in m.get("replacement", "")
            and m.get("original") != m.get("replacement")
        ):
            return True
    return False


def probe_mutate_source():
    """mutate_source returns one Mutant per mechanical change over parseable source, and a Fault dict when the source does not parse."""
    bad = []
    for case in _CASES:
        got = mutate_source(case["source"])

        if case["is_fault"]:
            if isinstance(got, list):
                bad.append(
                    f"mutate_source({case['name']}: unparseable) returned a list, "
                    f"expected a Fault dict with 'problem' and 'remedy'"
                )
                continue
            if not (isinstance(got, dict) and "problem" in got and "remedy" in got):
                bad.append(
                    f"mutate_source({case['name']}: unparseable) -> {got!r}, "
                    f"expected a Fault dict with 'problem' and 'remedy' keys"
                )
            continue

        if not isinstance(got, list):
            bad.append(
                f"mutate_source({case['name']}) -> {got!r}, expected a list of Mutant dicts"
            )
            continue

        present_kinds = {m.get("change_kind") for m in got}
        missing = case["must_contain_kinds"] - present_kinds
        if missing:
            bad.append(
                f"mutate_source({case['name']}) produced kinds {sorted(present_kinds)}, "
                f"missing required {sorted(missing)}"
            )

        for pin in case["pins"]:
            if not _pin_satisfied(got, pin):
                bad.append(
                    f"mutate_source({case['name']}) has no {pin['change_kind']} mutant "
                    f"with original containing {pin['original_has']!r} and replacement "
                    f"containing {pin['replacement_has']!r}"
                )
    return bad


def run():
    bad = probe_mutate_source()
    for line in bad:
        print(line)
    print(f"probe_mutate_source: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
