"""Conformance fragment for the control_characters scenario (honest-test.feature).

Scenario: control_characters generates the control-character neighbor class.
  Then for each C0 and C1 control code, DEL, and the zero-width and
  bidirectional-override characters on the injection set it returns three
  neighbors — the character prepended, appended, and inserted at the midpoint of
  value.
  And these reveal parsers that strip or mishandle control codes instead of
  rejecting them.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.control_characters
and returns a list of failure strings (empty when every case holds). No classes, no
mocks. The exact injection set is an implementation detail, so the probe asserts
structure, not the full set: the neighbor class is non-empty; every neighbor is
exactly one character longer than the input; every neighbor carries at least one
control/zero-width/bidi codepoint (unicodedata category Cc or Cf); and for each
representative injection character spanning the classes the note names, the three
placements appear — the character prepended, appended, and inserted somewhere in the
interior of the value.

The special-character predicate uses unicodedata, which is independent of the
function under test, so the oracle is not circular.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

import unicodedata

from honest_test import control_characters

# Representative injection characters spanning the classes the note names:
# a C0 control, DEL, a C1 control, a zero-width format char, and a bidi override.
_NUL = "\x00"  # C0 control (U+0000)
_DEL = "\x7f"  # DEL (U+007F)
_NEL = "\x85"  # C1 control, NEL (U+0085)
_ZWSP = "​"  # zero-width space (U+200B, category Cf)
_RLO = "‮"  # right-to-left override (U+202E, category Cf)

_REPRESENTATIVES = [
    ("NUL", _NUL),
    ("DEL", _DEL),
    ("C1-NEL", _NEL),
    ("ZWSP", _ZWSP),
    ("RLO", _RLO),
]

# At least two values, each long enough that an interior insertion is distinct from
# the prepend and append placements.
_CASES = [
    {"given": "abc", "reps": _REPRESENTATIVES},
    {"given": "hello", "reps": _REPRESENTATIVES},
]


def _is_special(ch):
    """True when ch is a control (Cc) or format (Cf) codepoint — the classes the note names."""
    return unicodedata.category(ch) in ("Cc", "Cf")


def _interior_insertions(value, ch):
    """Every neighbor formed by inserting ch strictly inside value (not prepend/append)."""
    return {value[:i] + ch + value[i:] for i in range(1, len(value))}


def probe_control_characters():
    """control_characters returns, for each injection character, the character prepended, appended, and inserted in the interior of value — every neighbor one codepoint longer and carrying a control/zero-width/bidi codepoint."""
    bad = []
    for case in _CASES:
        value = case["given"]
        got = control_characters(value=value)

        if not got:
            bad.append(
                f"control_characters(value={value!r}) returned no neighbors; "
                f"expected a non-empty control-character neighbor class"
            )
            continue

        for neighbor in got:
            if len(neighbor) != len(value) + 1:
                bad.append(
                    f"control_characters(value={value!r}) neighbor {neighbor!r} has "
                    f"length {len(neighbor)}, expected exactly {len(value) + 1}"
                )
            if not any(_is_special(ch) for ch in neighbor):
                bad.append(
                    f"control_characters(value={value!r}) neighbor {neighbor!r} carries "
                    f"no control/zero-width/bidi codepoint"
                )

        got_set = set(got)
        for label, ch in case["reps"]:
            if ch + value not in got_set:
                bad.append(
                    f"control_characters(value={value!r}) missing the {label} prepend "
                    f"neighbor {ch + value!r}"
                )
            if value + ch not in got_set:
                bad.append(
                    f"control_characters(value={value!r}) missing the {label} append "
                    f"neighbor {value + ch!r}"
                )
            interior = _interior_insertions(value, ch)
            if not (interior & got_set):
                bad.append(
                    f"control_characters(value={value!r}) missing an interior {label} "
                    f"insertion among {interior}"
                )
    return bad


def run():
    bad = probe_control_characters()
    for line in bad:
        print(line)
    print(f"probe_control_characters: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
