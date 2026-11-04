"""Conformance fragment for the supplied_cases scenario (honest-test.feature).

Scenario: supplied_cases resolves one predicate's programmer-supplied values from
  the config.
  Then it returns a SuppliedCases carrying that predicate's valid and invalid
  values when the config has an entry.
  And it returns missing true with empty lists when the config has no entry, the
  case the runner turns into a missing_supplied_values warning rather than
  passing over.
  And it reads no file: the supplied values entered through read_config at the
  boundary, and it reads only the record it was handed.
  And it returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.supplied_cases
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: SuppliedConfig and SuppliedCases are plain dicts, compared by value.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import supplied_cases

# A config with more than one predicate, so the lookup must pick the right one.
_CONFIG = {
    "is_country_code": {
        "valid": ["US", "CA", "FR"],
        "invalid": ["XX", "usa", ""],
        "strategy": "supplied_only",
    },
    "is_known_currency": {
        "valid": ["USD", "EUR"],
        "invalid": ["ZZZ"],
        "strategy": "supplied_only",
    },
}

_CASES = [
    # (a) predicate PRESENT: missing False, valid/invalid copied from its entry,
    #     and the lookup picks is_country_code out of the two-predicate config.
    {
        "given": {"predicate_name": "is_country_code", "supplied_values": _CONFIG},
        "expect": {
            "valid": ["US", "CA", "FR"],
            "invalid": ["XX", "usa", ""],
            "missing": False,
        },
    },
    # (a) the OTHER present predicate, to prove the lookup is by name not by
    #     position: the second entry's own lists, not the first's.
    {
        "given": {"predicate_name": "is_known_currency", "supplied_values": _CONFIG},
        "expect": {
            "valid": ["USD", "EUR"],
            "invalid": ["ZZZ"],
            "missing": False,
        },
    },
    # (b) predicate ABSENT: missing True with BOTH lists empty — the case the
    #     runner turns into a missing_supplied_values warning.
    {
        "given": {"predicate_name": "is_timezone", "supplied_values": _CONFIG},
        "expect": {"valid": [], "invalid": [], "missing": True},
    },
    # (b) absent against the empty config: same missing-True, both lists empty.
    {
        "given": {"predicate_name": "anything", "supplied_values": {}},
        "expect": {"valid": [], "invalid": [], "missing": True},
    },
]


def probe_supplied_cases():
    """supplied_cases returns one predicate's supplied valid and invalid values when the config holds it, and missing true with two empty lists when it does not."""
    bad = []
    for case in _CASES:
        got = supplied_cases(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"supplied_cases({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_supplied_cases()
    for line in bad:
        print(line)
    print(f"probe_supplied_cases: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
