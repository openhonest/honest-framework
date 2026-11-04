"""Conformance fragment for the unicode_confusables scenario (honest-test.feature).

Scenario: unicode_confusables generates the Unicode-confusable neighbor class.
  Then for each ASCII character in value that has a known visually-similar
  character in a different Unicode block, it produces one neighbor with that
  character substituted at that position, plus one full-homoglyph neighbor with
  every replaceable character substituted at once (section 3.5). The confusable
  map is the curated subset of Unicode Technical Standard 39 the reference
  implementation exercises. A value with no confusable character produces no
  neighbor.

The exact confusable map is an implementation detail, so this probe asserts the
STRUCTURE the contract fixes, never an exact codepoint set: the per-position
substitution preserves length, the full-homoglyph neighbor substitutes every
confusable position at once, every neighbor differs from the input and carries a
non-ASCII codepoint, and a value with no confusable character yields nothing.

Cases are data; one pure probe feeds them to the real honest_test function and
returns a list of failure strings (empty when every case holds). No classes, no
mocks: it calls the real honest_test.unicode_confusables.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import unicode_confusables

# "paypal" carries the classic Latin/Cyrillic homoglyphs: 'a' -> Cyrillic 'а',
# plus 'o', 'e', 'p' are standard confusables. The exact substitutes are not
# pinned; the structure the contract fixes is.
#
# "012345" is all digits with no confusable ASCII letter, so it names the
# scenario's absence case: no neighbor.
_CASES = [
    {
        "given": {"value": "paypal"},
        # At least one neighbor exists, and the per-position + full-homoglyph
        # structure below must hold.
        "has_neighbors": True,
    },
    {
        "given": {"value": "paper"},
        "has_neighbors": True,
    },
    {
        # The explicit absence case: no confusable character, so no neighbor.
        "given": {"value": "012345"},
        "has_neighbors": False,
    },
]


def _confusable_positions(value, neighbor):
    """The positions where a same-length neighbor differs from value."""
    return [i for i, (a, b) in enumerate(zip(value, neighbor)) if a != b]


def probe_unicode_confusables():
    """unicode_confusables substitutes each confusable ASCII character one at a time, plus one full-homoglyph neighbor changing every confusable position at once, and produces nothing for a value with no confusable character."""
    bad = []
    for case in _CASES:
        value = case["given"]["value"]
        got = unicode_confusables(value)

        if not isinstance(got, list):
            bad.append(f"unicode_confusables({value!r}) -> {got!r}, expected a list")
            continue

        if not case["has_neighbors"]:
            # Absence case: a value with no confusable character yields nothing.
            if got:
                bad.append(
                    f"unicode_confusables({value!r}) -> {got!r}, "
                    f"expected no neighbors (value has no confusable character)"
                )
            continue

        # (a) the list is non-empty.
        if not got:
            bad.append(
                f"unicode_confusables({value!r}) -> [], "
                f"expected at least one confusable neighbor"
            )
            continue

        # (c) every neighbor differs from the input in at least one position.
        same_as_input = [n for n in got if n == value]
        if same_as_input:
            bad.append(
                f"unicode_confusables({value!r}) returned a neighbor equal to the "
                f"input: {same_as_input!r}"
            )

        # (d) at least one neighbor carries a non-ASCII codepoint (ord > 127).
        if not any(any(ord(ch) > 127 for ch in n) for n in got):
            bad.append(
                f"unicode_confusables({value!r}) -> {got!r}, expected at least one "
                f"neighbor with a non-ASCII codepoint"
            )

        # (b) every same-length neighbor differs in at least one position, and a
        # per-position substitution changes exactly one position. A neighbor of
        # a different length is the full-homoglyph variant, allowed to differ.
        same_len = [n for n in got if len(n) == len(value)]
        single_pos = [n for n in same_len if len(_confusable_positions(value, n)) == 1]
        if not single_pos:
            bad.append(
                f"unicode_confusables({value!r}) -> {got!r}, expected at least one "
                f"single-position substitution neighbor (same length, one position "
                f"changed)"
            )

        # (e) the full-homoglyph neighbor: the one that changed the most
        # positions. It must change strictly more positions than any single
        # per-position substitution, i.e. more than one confusable position.
        same_len_changes = [
            len(_confusable_positions(value, n)) for n in same_len
        ]
        if same_len_changes:
            most = max(same_len_changes)
            if most < 2:
                bad.append(
                    f"unicode_confusables({value!r}) -> {got!r}, expected a "
                    f"full-homoglyph neighbor changing more than one confusable "
                    f"position at once; the most any neighbor changed was {most}"
                )
        else:
            bad.append(
                f"unicode_confusables({value!r}) -> {got!r}, expected a "
                f"same-length full-homoglyph neighbor"
            )
    return bad


def run():
    bad = probe_unicode_confusables()
    for line in bad:
        print(line)
    print(f"probe_unicode_confusables: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
