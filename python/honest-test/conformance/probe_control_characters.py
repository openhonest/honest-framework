"""honest-test conformance: control_characters — the control-character neighbor class.

The spec fixes the injection set exactly (§3.5, class 3): 16 characters — the C0 controls
NULL, BACKSPACE, TAB, LINE FEED, CARRIAGE RETURN, ESC, DEL, plus the zero-width and
bidirectional-override characters. For each, three neighbors: the character prepended,
appended, and inserted at the midpoint of the value. This probe carries that set as its
oracle and asserts the real control_characters produces exactly those neighbors.

No classes, no mocks. It calls the real honest_test.control_characters and compares sets.
"""

from honest_test import control_characters

_INJECTION = [
    "\x00", "\x08", "\x09", "\x0a", "\x0d", "\x1b", "\x7f",
    "​", "‎", "‏", "‪", "‫",
    "‬", "‭", "‮", "﻿",
]


def _reference(value):
    """The §3.5 class-3 algorithm transcribed from the spec, the known-good oracle."""
    results = []
    for c in _INJECTION:
        results.append(c + value)
        results.append(value + c)
        mid = len(value) // 2
        results.append(value[:mid] + c + value[mid:])
    return results


def probe_control_characters():
    bad = []
    for value in ["AB", "abc"]:
        got = control_characters(value)
        if not isinstance(got, list):
            bad.append(f"control_characters({value!r}) -> {type(got).__name__}, expected a list")
            continue
        expected = set(_reference(value))
        got_set = set(got)
        missing = expected - got_set
        extra = got_set - expected
        if missing:
            bad.append(f"control_characters({value!r}) is missing {len(missing)} of the 48 neighbors")
        if extra:
            bad.append(f"control_characters({value!r}) produced {len(extra)} neighbors not in the §3.5 injection set")
    return bad


def run():
    messages = probe_control_characters()
    if messages:
        print(f"FAIL HTEST-probe [control_characters]: {messages}")
    print(f"control_characters: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
