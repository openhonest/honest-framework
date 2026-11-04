"""Conformance fragment for the edit_distance_1 scenario (honest-test.feature).

Scenario: edit_distance_1 generates the edit-distance-1 neighbor class.
  Then it returns every single deletion, every single insertion from the
  alphanumeric alphabet, every single substitution, the lower, upper and title
  case variants, and the whitespace variants — a leading space, a trailing
  space, and an interior space after the first character.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.edit_distance_1.

The full neighbor set is large, so each case asserts MEMBERSHIP and structure:
the named neighbors from each sub-class (deletion, substitution, insertion, case,
whitespace) must be PRESENT, and the identity value must be ABSENT (edit-distance-1
excludes the original). This is its own fragment file; run_conformance.py,
suite.json and laws_htest.py are untouched.
"""

from honest_test import edit_distance_1

_CASES = [
    {
        "value": "ab",
        # Each entry pins one named neighbor from one sub-class of the note.
        "present": [
            "a",  # deletion: drop the second character
            "b",  # deletion: drop the first character
            "cb",  # substitution: position 0 'a' -> 'c' (alphanumeric)
            "ac",  # substitution: position 1 'b' -> 'c' (alphanumeric)
            "zab",  # insertion: 'z' before position 0 (alphanumeric)
            "abz",  # insertion: 'z' after the last character
            "AB",  # upper-case variant
            "Ab",  # title-case variant
            " ab",  # whitespace: a leading space
            "ab ",  # whitespace: a trailing space
            "a b",  # whitespace: an interior space after the first character
        ],
        # Edit-distance-1 excludes the identity.
        "absent": ["ab"],
    },
    {
        "value": "xy",
        "present": [
            "x",  # deletion: drop the second character
            "y",  # deletion: drop the first character
            "zy",  # substitution: position 0 'x' -> 'z' (alphanumeric)
            "zxy",  # insertion: 'z' before position 0 (alphanumeric)
            "XY",  # upper-case variant
            "Xy",  # title-case variant
            " xy",  # whitespace: a leading space
            "xy ",  # whitespace: a trailing space
            "x y",  # whitespace: an interior space after the first character
        ],
        "absent": ["xy"],
    },
]


def probe_edit_distance_1():
    """edit_distance_1 produces every deletion, insertion, substitution, case variant and whitespace variant of the value, and never the value itself."""
    bad = []
    for case in _CASES:
        got = edit_distance_1(case["value"])
        got_set = set(got)
        for neighbor in case["present"]:
            if neighbor not in got_set:
                bad.append(
                    f"edit_distance_1({case['value']!r}) is missing {neighbor!r}"
                )
        for neighbor in case["absent"]:
            if neighbor in got_set:
                bad.append(
                    f"edit_distance_1({case['value']!r}) wrongly includes {neighbor!r}"
                )
    return bad


def run():
    bad = probe_edit_distance_1()
    for line in bad:
        print(line)
    print(f"probe_edit_distance_1: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
