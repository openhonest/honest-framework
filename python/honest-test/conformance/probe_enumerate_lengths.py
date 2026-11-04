"""Conformance fragment for the enumerate_lengths scenario (honest-test.feature).

Scenario: enumerate_lengths generates the strings for a length-bounded predicate.
  Then it reads the minimum and maximum length from the comparison operators the
  node holds, distinguishing == (one exact length) from <= (a range up to a
  maximum) from < (a range up to one below).
  And it returns a LengthCases with one valid string at every length in the range,
  built by repeating the alphabet so lengths beyond the alphabet are still generated.
  And the invalid list carries the boundary lengths just outside — one over the
  maximum always, and one under the minimum when the minimum exceeds one.

The alphabet and the repetition rule are fixed by section 3.4 of
../specs/02-code-quality/honest-test-architecture.md:

    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    string_of_length(n, chars) repeats chars to length n.

So the exact strings are pinned, not an implementation detail, and this probe
asserts their exact content. The expected strings below are written out as
literals, never computed from the function under test, so a stub cannot pass.

Inputs are built through the real pipeline: parse_source -> extract_predicates ->
enumerate_lengths. No classes, no mocks; this is its own fragment file so the
other scenarios' fragments never collide with it.
"""

from honest_test import enumerate_lengths, extract_predicates, parse_source

_CASES = [
    # len(s) <= 5: (min, max) = (1, 5). Valid is one string at lengths 1..5.
    # min == 1, so the one-under case is the empty string and is NOT emitted here
    # (it is an empty_token rejection, section 9.3). Only one over the max: length 6.
    {
        "source": "recognize = lambda s: len(s) <= 5\n",
        "expect_valid": ["a", "ab", "abc", "abcd", "abcde"],
        "expect_invalid": {"abcdef"},
    },
    # len(s) == 3: (min, max) = (3, 3), exact length. Valid is the single length-3
    # string. min == max == 3 > 1, so invalid carries one over (length 4) and one
    # under (length 2).
    {
        "source": "recognize = lambda s: len(s) == 3\n",
        "expect_valid": ["abc"],
        "expect_invalid": {"abcd", "ab"},
    },
    # 2 <= len(s) <= 8: (min, max) = (2, 8). Valid is lengths 2..8. min == 2 > 1,
    # so invalid carries one over (length 9) and one under (length 1).
    {
        "source": "recognize = lambda s: 2 <= len(s) <= 8\n",
        "expect_valid": [
            "ab",
            "abc",
            "abcd",
            "abcde",
            "abcdef",
            "abcdefg",
            "abcdefgh",
        ],
        "expect_invalid": {"a", "abcdefghi"},
    },
]


def _predicate_node(source):
    """The one length-bounded predicate node, built by the real parse pipeline."""
    tree = parse_source(source)
    nodes = extract_predicates(tree)
    return nodes[0]


def probe_enumerate_lengths():
    """enumerate_lengths reads the operator for (min, max) and returns one valid string per in-range length plus the boundary lengths just outside — one over the max always, one under the min when min > 1."""
    bad = []
    for case in _CASES:
        node = _predicate_node(case["source"])
        got = enumerate_lengths(node)
        if got["valid"] != case["expect_valid"]:
            bad.append(
                f"enumerate_lengths({case['source']!r}).valid -> {got['valid']}, "
                f"expected {case['expect_valid']}"
            )
        if set(got["invalid"]) != case["expect_invalid"]:
            bad.append(
                f"enumerate_lengths({case['source']!r}).invalid -> "
                f"{set(got['invalid'])}, expected {case['expect_invalid']}"
            )
    return bad


def run():
    bad = probe_enumerate_lengths()
    for line in bad:
        print(line)
    print(f"probe_enumerate_lengths: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
