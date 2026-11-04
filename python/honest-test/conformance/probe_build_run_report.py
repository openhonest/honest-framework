"""Conformance fragment for the build_run_report scenario (honest-test.feature).

Scenario: build_run_report assembles the RunReport from the measured parts.
  Then it returns a RunReport record carrying the counts the run measured, so a
  pure function produces the report rather than an orchestrator assembling it
  inline. It reads its arguments as data and touches no world.

build_run_report is a pure assembler: each of its nine arguments must land in its
correctly-named RunReport field and none may be swapped. Every int input is a
distinct value so mis-wiring any one field is caught. coverage is the exact
CoverageReport passed in.

Cases are data; one pure probe feeds them to the real honest_test.build_run_report
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: plain dicts in, plain dict out, compared by value.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import build_run_report

# Two plain-dict CoverageReports, one per case, each the exact value the matching
# row must carry straight through into the RunReport's coverage field.
_COVERAGE_A = {
    "version": "1.0",
    "vocabularies": {},
    "chains": {},
    "honesty": {},
    "state_machines": {},
}
_COVERAGE_B = {
    "version": "1.0",
    "vocabularies": {"color": {"total": 5, "exercised": 5, "pct": 100}},
    "chains": {},
    "honesty": {},
    "state_machines": {},
}

_CASES = [
    # Every int distinct so a field-swap bug fails. coverage is _COVERAGE_A.
    {
        "given": {
            "chains": 2,
            "links": 7,
            "vocabularies": 3,
            "permutations": 3000,
            "failures": 4,
            "adversarial_rejected": 11,
            "coverage": _COVERAGE_A,
            "mutation_caught": 40,
            "mutation_total": 42,
        },
        "expect": {
            "chains": 2,
            "links": 7,
            "vocabularies": 3,
            "permutations": 3000,
            "failures": 4,
            "adversarial_rejected": 11,
            "coverage": _COVERAGE_A,
            "mutation_caught": 40,
            "mutation_total": 42,
        },
    },
    # A second row with different values, including a non-empty CoverageReport.
    {
        "given": {
            "chains": 1,
            "links": 9,
            "vocabularies": 5,
            "permutations": 128,
            "failures": 0,
            "adversarial_rejected": 6,
            "coverage": _COVERAGE_B,
            "mutation_caught": 17,
            "mutation_total": 20,
        },
        "expect": {
            "chains": 1,
            "links": 9,
            "vocabularies": 5,
            "permutations": 128,
            "failures": 0,
            "adversarial_rejected": 6,
            "coverage": _COVERAGE_B,
            "mutation_caught": 17,
            "mutation_total": 20,
        },
    },
]


def probe_build_run_report():
    """build_run_report lands each measured argument in its correctly-named RunReport field, carrying the CoverageReport through unchanged, reading no world."""
    bad = []
    for case in _CASES:
        got = build_run_report(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"build_run_report({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_build_run_report()
    for line in bad:
        print(line)
    print(f"probe_build_run_report: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
