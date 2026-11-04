"""Conformance fragment for the coverage_ratio scenario (honest-test.feature).

Scenario: coverage_ratio computes one coverage dimension's numbers.
  Then it returns a Coverage carrying exercised, total and their whole-number
  percentage — the share of the things that could be exercised that were, one
  computation for all four dimensions.
  And it reads no world and returns pure data.

Coverage is honest-type's record idiom, a plain dict
{"total": int, "exercised": int, "pct": int}. pct is exercised over total as a
whole-number percentage (honest-test.hd, type Coverage, section 9).

Cases are data; one pure probe feeds them to the real coverage_ratio and returns
a list of failure strings (empty when every case holds). No classes, no mocks: it
calls the real honest_test.coverage_ratio and asserts all three fields by key.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import coverage_ratio

_CASES = [
    # A clean fraction: 3 of 4 is 75 percent.
    {
        "given": {"exercised": 3, "total": 4},
        "expect": {"total": 4, "exercised": 3, "pct": 75},
    },
    # Full coverage: exercised equals total, 100 percent.
    {
        "given": {"exercised": 5, "total": 5},
        "expect": {"total": 5, "exercised": 5, "pct": 100},
    },
    # The explicit zero case: nothing exercised is 0 percent.
    {
        "given": {"exercised": 0, "total": 10},
        "expect": {"total": 10, "exercised": 0, "pct": 0},
    },
    # A rounding case pinned to a fraction that is unambiguous: 1 of 3 is
    # 33.33..., which is 33 under floor, round and truncate alike, so the whole
    # case holds whatever whole-number rule the note leaves unstated.
    {
        "given": {"exercised": 1, "total": 3},
        "expect": {"total": 3, "exercised": 1, "pct": 33},
    },
]


def probe_coverage_ratio():
    """coverage_ratio returns a Coverage carrying exercised, total and their whole-number percentage."""
    bad = []
    for case in _CASES:
        got = coverage_ratio(**case["given"])
        want = case["expect"]
        for field in ("total", "exercised", "pct"):
            if got.get(field) != want[field]:
                bad.append(
                    f"coverage_ratio({case['given']}) -> {field}={got.get(field)}, "
                    f"expected {field}={want[field]}"
                )
    return bad


def run():
    bad = probe_coverage_ratio()
    for line in bad:
        print(line)
    print(f"probe_coverage_ratio: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
