"""honest-test conformance: edit_distance_1 — the edit-distance-1 neighbor class.

The spec fixes this algorithm exactly (§3.5, class 1): every single deletion, every
single insertion from the 62-character alphanumeric alphabet, every single substitution,
the lower, upper and title case variants, and the whitespace variants — a leading space,
a trailing space, and an interior space after the first character. This probe carries that
reference algorithm as its oracle and asserts the real edit_distance_1 produces the same
set of neighbors on known inputs.

No classes, no mocks. It calls the real honest_test.edit_distance_1 and compares sets.
"""

from honest_test import edit_distance_1

_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _reference(value):
    """The §3.5 class-1 algorithm transcribed from the spec, the known-good oracle."""
    results = []
    chars = list(value)
    for i in range(len(chars)):
        results.append("".join(chars[:i] + chars[i + 1:]))
    for i in range(len(chars) + 1):
        for c in _ALPHA:
            results.append("".join(chars[:i] + [c] + chars[i:]))
    for i in range(len(chars)):
        for c in _ALPHA:
            if c != chars[i]:
                results.append("".join(chars[:i] + [c] + chars[i + 1:]))
    results.append(value.lower())
    results.append(value.upper())
    results.append(value.title())
    results.append(" " + value)
    results.append(value + " ")
    if len(value) >= 2:
        results.append(value[0] + " " + value[1:])
    return results


def probe_edit_distance_1():
    bad = []
    for value in ["Ab", "x7"]:
        got = edit_distance_1(value)
        if not isinstance(got, list):
            bad.append(f"edit_distance_1({value!r}) -> {type(got).__name__}, expected a list")
            continue
        expected = set(_reference(value))
        got_set = set(got)
        missing = expected - got_set
        extra = got_set - expected
        if missing:
            bad.append(f"edit_distance_1({value!r}) is missing {sorted(missing)[:6]}")
        if extra:
            bad.append(f"edit_distance_1({value!r}) produced unexpected {sorted(extra)[:6]}")
    return bad


def run():
    messages = probe_edit_distance_1()
    if messages:
        print(f"FAIL HTEST-probe [edit_distance_1]: {messages}")
    print(f"edit_distance_1: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
