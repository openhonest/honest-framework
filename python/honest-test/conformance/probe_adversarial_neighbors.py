"""Conformance fragment for the adversarial_neighbors scenario (honest-test.feature).

Scenario: adversarial_neighbors generates the five classes of adversarial
  neighbors of one value.
  Then it returns the deduplicated union of edit-distance-1 neighbors, Unicode
  confusables, control-character injections, length extensions and encoding
  variants, with the original value removed.

This probe asserts the union-and-dedup contract, not the exact membership of each
class (sibling probes cover the five class functions). For a short value it pins:
  (a) the result is non-empty and large;
  (b) the original value is NOT present (it is removed);
  (c) there are no duplicate entries (dedup: len(list) == len(set(list)));
  (d) representative members from several classes are present at once -- an
      edit-distance deletion, a case variant, a length repetition, a
      control-character injection ('\\x00'), and a neighbor with a non-ASCII
      codepoint.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.adversarial_neighbors. It does not import the five class
functions; it only calls adversarial_neighbors itself.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import adversarial_neighbors

_CASES = [
    {
        # "ab": deleting 'b' yields "a"; upper-casing yields "AB"; a length
        # extension repeats the value ("ab" * 10). A control-character injection
        # puts '\x00' into some neighbor; a confusable / encoding variant puts a
        # non-ASCII codepoint into some neighbor.
        "value": "ab",
        "required_members": ["a", "AB", "ab" * 10],
        "min_count": 20,
    },
    {
        # "x7": deleting 'x' yields "7"; upper-casing yields "X7" (7 has no
        # case); "x7" * 10 is the repetition length extension.
        "value": "x7",
        "required_members": ["7", "X7", "x7" * 10],
        "min_count": 20,
    },
]


def _has_control(neighbors):
    """True when some neighbor carries a NUL control character."""
    return any("\x00" in n for n in neighbors)


def _has_non_ascii(neighbors):
    """True when some neighbor carries a codepoint above the ASCII range."""
    return any(any(ord(c) > 127 for c in n) for n in neighbors)


def probe_adversarial_neighbors():
    """adversarial_neighbors returns the deduplicated union of the five neighbor classes with the original value removed."""
    bad = []
    for case in _CASES:
        value = case["value"]
        got = adversarial_neighbors(value)

        # (a) non-empty and large
        if len(got) < case["min_count"]:
            bad.append(
                f"adversarial_neighbors({value!r}) produced {len(got)} neighbors, "
                f"expected at least {case['min_count']}"
            )

        # (b) the original value is removed
        if value in got:
            bad.append(
                f"adversarial_neighbors({value!r}) still contains the original "
                f"value {value!r}, which must be removed"
            )

        # (c) no duplicates (union, not naive concatenation)
        if len(got) != len(set(got)):
            dupes = len(got) - len(set(got))
            bad.append(
                f"adversarial_neighbors({value!r}) has {dupes} duplicate entry(ies); "
                f"the union must be deduplicated (len {len(got)} != set len {len(set(got))})"
            )

        # (d) representative members from several classes
        for member in case["required_members"]:
            if member not in got:
                bad.append(
                    f"adversarial_neighbors({value!r}) is missing representative "
                    f"neighbor {member!r}"
                )
        if not _has_control(got):
            bad.append(
                f"adversarial_neighbors({value!r}) has no control-character neighbor "
                f"(none containing '\\x00')"
            )
        if not _has_non_ascii(got):
            bad.append(
                f"adversarial_neighbors({value!r}) has no neighbor with a non-ASCII "
                f"codepoint (confusable or encoding variant)"
            )
    return bad


def run():
    bad = probe_adversarial_neighbors()
    for line in bad:
        print(line)
    print(f"probe_adversarial_neighbors: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
