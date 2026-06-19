"""Numeric predicate generation (section 3.3).

For predicates classified Numeric, generate values from the Fibonacci sequence in both
directions from zero, up to a limit. The logarithmic spacing gives natural density at small
numbers and widening gaps at large ones, probing boundary conditions without exhaustive
enumeration. Floats are the integer sequence divided by 100.
"""

DEFAULT_LIMIT = 1_000_000


def fibonacci_sequence(limit=DEFAULT_LIMIT):
    """Fibonacci values in both directions from zero, up to `limit` (section 3.3): the
    negatives (largest magnitude first) followed by the non-negative sequence."""
    seq = [0, 1]
    while seq[-1] < limit:
        seq.append(seq[-2] + seq[-1])
    negative = [-value for value in seq if value > 0]
    return negative + seq


def numeric_values(limit=DEFAULT_LIMIT, negative=True, as_float=False):
    """Test values for a numeric predicate (section 3.3). `negative=False` drops values below
    zero (e.g. a non-negative amount); `as_float=True` yields each Fibonacci number / 100."""
    sequence = fibonacci_sequence(limit)
    if not negative:
        sequence = [value for value in sequence if value >= 0]
    if as_float:
        return [value / 100 for value in sequence]
    return sequence
