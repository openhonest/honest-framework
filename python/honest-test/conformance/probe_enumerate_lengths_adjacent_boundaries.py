# scenario: enumerate_lengths returns valid lengths and adjacent rejection boundaries
# inherits: hd=python/honest-test/honest-test-pure.hd::enumerate_lengths -> feature=specs/features/honest-test.feature::enumerate_lengths returns valid lengths and adjacent rejection boundaries
"""Generate exactly one string at each declared length, including past one alphabet."""

from honest_parse import parse
from honest_test import enumerate_lengths

_CASES = [
    ("len(s) == 5", [5], [4, 6]),
    ("len(s) <= 8", [1, 2, 3, 4, 5, 6, 7, 8], [9]),
    ("len(s) < 8", [1, 2, 3, 4, 5, 6, 7], [8]),
    ("3 <= len(s) <= 8", [3, 4, 5, 6, 7, 8], [2, 9]),
    ("2 <= len(s) <= 3", [2, 3], [1, 4]),
    ("3 < len(s) < 8", [4, 5, 6, 7], [3, 8]),
    ("len(s) == 37", [37], [36, 38]),
]
_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def probe_enumerate_lengths_adjacent_boundaries():
    failures = []
    for expression, valid_lengths, invalid_lengths in _CASES:
        source = f"def candidate(s):\n    return {expression}\n".encode()
        tree = parse(source, "python")
        body = tree.root_node.named_children[0].child_by_field_name("body")
        actual = enumerate_lengths(body)
        expected = {"valid": valid_lengths, "invalid": invalid_lengths}
        for side, lengths in expected.items():
            strings = actual[side]
            if not all(isinstance(value, str) for value in strings) or sorted(map(len, strings)) != lengths:
                failures.append(f"enumerate_lengths({expression!r}) {side} returned {strings!r}, expected lengths {lengths!r}")
            long_strings = {value for value in strings if isinstance(value, str) and len(value) > len(_ALPHABET)}
            if any(value != (_ALPHABET + _ALPHABET)[:len(value)] for value in long_strings):
                failures.append(f"enumerate_lengths({expression!r}) {side} did not repeat the alphabet: {long_strings!r}")
    return failures


def run():
    failures = probe_enumerate_lengths_adjacent_boundaries()
    for failure in failures:
        print(failure)
    return len(failures)
