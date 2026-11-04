"""Conformance fragment for the build_coverage_report scenario (honest-test.feature).

Scenario: build_coverage_report assembles the four coverage dimensions into the
  CoverageReport.
  Then it returns the CoverageReport, stamping the format version, which
  write_coverage writes as coverage.json and honest-check reads for HC-P009.
  And each argument is a map from a declaration's name to its Coverage, already
  computed by coverage_ratio.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.build_coverage_report and compares the returned dict by value.

A Coverage is {"total": n, "exercised": m, "pct": p}. A CoverageReport is
{"version": s, "vocabularies": ..., "chains": ..., "honesty": ...,
"state_machines": ...} where each dimension is a dict<str, Coverage>. The .hd note
says the format version string is '1.0'.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import build_coverage_report

# Four distinct Coverage records, one per dimension, so a swapped slot is caught.
_VOCAB = {"total": 10, "exercised": 10, "pct": 100}
_VOCAB2 = {"total": 4, "exercised": 2, "pct": 50}
_CHAIN = {"total": 6, "exercised": 3, "pct": 50}
_HONESTY = {"total": 8, "exercised": 7, "pct": 87}
_SM = {"total": 2, "exercised": 2, "pct": 100}

_CASES = [
    # (a) All four dimensions populated. Vocabularies carries two named entries,
    # the others one each. Every dimension must land in its own slot (not swapped)
    # and the version must be stamped '1.0'. Written out literally so a stub
    # returning {} or an empty report cannot pass.
    {
        "given": {
            "vocabularies": {"color": _VOCAB, "size": _VOCAB2},
            "chains": {"pipeline": _CHAIN},
            "honesty": {"pipeline": _HONESTY},
            "state_machines": {"door": _SM},
        },
        "expect": {
            "version": "1.0",
            "vocabularies": {"color": _VOCAB, "size": _VOCAB2},
            "chains": {"pipeline": _CHAIN},
            "honesty": {"pipeline": _HONESTY},
            "state_machines": {"door": _SM},
        },
    },
    # (b) All four empty -> a CoverageReport with version '1.0' and four empty
    # dimension maps. The explicit "or nothing" boundary case.
    {
        "given": {
            "vocabularies": {},
            "chains": {},
            "honesty": {},
            "state_machines": {},
        },
        "expect": {
            "version": "1.0",
            "vocabularies": {},
            "chains": {},
            "honesty": {},
            "state_machines": {},
        },
    },
]


def probe_build_coverage_report():
    """build_coverage_report maps each of the four dimensions verbatim into its own slot and stamps the format version '1.0'."""
    bad = []
    for case in _CASES:
        got = build_coverage_report(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"build_coverage_report({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_build_coverage_report()
    for line in bad:
        print(line)
    print(f"probe_build_coverage_report: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
