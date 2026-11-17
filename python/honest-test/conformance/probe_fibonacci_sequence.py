"""RED probe for honest-test.fibonacci_sequence — the numeric probe generator (.hd, spec section 3.3).

fibonacci_sequence builds the Fibonacci sequence from zero up to limit: the
negatives followed by the non-negatives when negative is true, the non-negatives
alone when it is false. The sequence seeds [0, 1] and appends the sum of the last
two while the last is below limit; the negatives are the strictly-positive terms
negated. It reads no world and returns a list of ints.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_test import fibonacci_sequence


def probe_fibonacci_sequence():
    """fibonacci_sequence returns the exact sequence for a given limit, folds the
    negative direction in only when asked, and keeps the duplicate 1 the seed
    produces."""
    bad = []

    # limit 10: seq seeds [0,1] and grows 1,2,3,5,8,13 (stops once 13 >= 10).
    # positives = [0,1,1,2,3,5,8,13]; negatives = the positive terms negated.
    pos_10 = [0, 1, 1, 2, 3, 5, 8, 13]
    neg_10 = [-1, -1, -2, -3, -5, -8, -13]

    cases = [
        # (limit, negative, expected)
        (10, False, pos_10),
        (10, True, neg_10 + pos_10),
        (1, False, [0, 1]),                       # 1 >= limit immediately, no growth
        (1, True, [-1, 0, 1]),                    # the single positive term 1 negated, then 0,1
        (2, False, [0, 1, 1, 2]),                 # grows once to 2, which stops it
        (2, True, [-1, -1, -2, 0, 1, 1, 2]),
    ]

    for limit, negative, expected in cases:
        got = fibonacci_sequence(limit, negative)
        if got != expected:
            bad.append(
                f"fibonacci_sequence({limit}, {negative}) = {got!r}, expected {expected!r}"
            )

    # The non-negative direction is always a prefix-free suffix: with negative=False
    # every value is >= 0, and the sequence is non-decreasing after the seed.
    plain = fibonacci_sequence(100, False)
    if any(v < 0 for v in plain):
        bad.append(f"negative=False must yield no negative values: {plain!r}")
    if plain[0] != 0:
        bad.append(f"the sequence must start at 0, got {plain[0]!r}")

    return bad


def run():
    failures = probe_fibonacci_sequence()
    for message in failures:
        print(f"FAIL fibonacci_sequence: {message}")
    print(f"fibonacci_sequence probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
