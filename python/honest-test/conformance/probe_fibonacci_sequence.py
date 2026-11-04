"""Conformance fragment for the fibonacci_sequence scenario (honest-test.feature).

Scenario: fibonacci_sequence generates the numeric probe values from zero up to
  the limit.
  Then it returns the Fibonacci sequence from zero up to limit, giving
  logarithmically distributed values dense among small numbers and spaced among
  large ones, probing a numeric range rather than enumerating it.
  And when negative is true it returns the negatives of the sequence prepended to
  the non-negatives, and the non-negatives alone otherwise.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.fibonacci_sequence.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py / suite.json are untouched.
"""

from honest_test import fibonacci_sequence

_CASES = [
    # The non-negative direction, fully fixed by the scenario's own example:
    # the Fibonacci terms from zero up to 10 are 0, 1, 1, 2, 3, 5, 8 (13 > 10).
    # Written out by hand so a stub returning [] cannot pass.
    {
        "given": {"limit": 10, "negative": False},
        "expect": [0, 1, 1, 2, 3, 5, 8],
    },
    # A smaller non-negative ceiling: terms up to 4 are 0, 1, 1, 2, 3 (5 > 4).
    {
        "given": {"limit": 4, "negative": False},
        "expect": [0, 1, 1, 2, 3],
    },
    # Another non-negative ceiling: terms up to 6 are 0, 1, 1, 2, 3, 5 (8 > 6).
    {
        "given": {"limit": 6, "negative": False},
        "expect": [0, 1, 1, 2, 3, 5],
    },
    # The negative direction for limit 10: the negated positive terms prepended in
    # number-line order, zero appearing once, then the non-negatives.
    {
        "given": {"limit": 10, "negative": True},
        "expect": [-8, -5, -3, -2, -1, -1, 0, 1, 1, 2, 3, 5, 8],
    },
    # The negative direction for limit 4: the negated positive terms (1, 1, 2, 3)
    # prepended in number-line order, zero once, then the non-negatives.
    {
        "given": {"limit": 4, "negative": True},
        "expect": [-3, -2, -1, -1, 0, 1, 1, 2, 3],
    },
]


def probe_fibonacci_sequence():
    """fibonacci_sequence returns the Fibonacci terms from zero up to limit, the negatives prepended when negative is true and the non-negatives alone otherwise."""
    bad = []
    for case in _CASES:
        got = fibonacci_sequence(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"fibonacci_sequence({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_fibonacci_sequence()
    for line in bad:
        print(line)
    print(f"probe_fibonacci_sequence: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
