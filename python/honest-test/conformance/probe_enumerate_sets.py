"""Conformance fragment for the enumerate_sets scenario (honest-test.feature).

Scenario: enumerate_sets generates every test case for a Set-based vocabulary.
  Then it enumerates every member of every Set recognizer and produces the
  Cartesian product of their members, with no sampling, so a vocabulary of three
  Sets of 5, 150 and 4 members yields all 3,000 cases.
  And it returns the list of test manifests, one per combination.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_type.vocabulary to build the input and the real
honest_test.enumerate_sets to produce the output.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import vocabulary

from honest_test import enumerate_sets

# 150 distinct members for the scenario's own 5 x 150 x 4 = 3000 literal.
_B150 = {f"b{i}" for i in range(150)}

_CASES = [
    # Two Sets of two members: the Cartesian product is the four manifests below,
    # written out by hand so a stub returning [] cannot pass.
    {
        "given": {"color": {"red", "green"}, "size": {"small", "large"}},
        "expect_count": 4,
        "expect_manifests": [
            {"color": "red", "size": "small"},
            {"color": "red", "size": "large"},
            {"color": "green", "size": "small"},
            {"color": "green", "size": "large"},
        ],
    },
    # A singleton Set yields exactly one manifest, its one member.
    {
        "given": {"only": {"x"}},
        "expect_count": 1,
        "expect_manifests": [{"only": "x"}],
    },
    # The scenario's own count literal: three Sets of 5, 150 and 4 members yield
    # all 3,000 cases, no sampling. Content is not spelled out; the count is.
    {
        "given": {
            "a": {"a0", "a1", "a2", "a3", "a4"},
            "b": _B150,
            "c": {"c0", "c1", "c2", "c3"},
        },
        "expect_count": 3000,
        "expect_manifests": None,
    },
]


def _as_set(manifests):
    """A list of manifest dicts as a hashable set, so order is not asserted."""
    return {frozenset(m.items()) for m in manifests}


def probe_enumerate_sets():
    """enumerate_sets yields the full Cartesian product of every Set member, one manifest per combination, with no sampling."""
    bad = []
    for case in _CASES:
        vocab = vocabulary(case["given"])
        got = enumerate_sets(vocab)
        if len(got) != case["expect_count"]:
            bad.append(
                f"enumerate_sets({case['given']}) produced {len(got)} manifests, "
                f"expected {case['expect_count']}"
            )
            continue
        if case["expect_manifests"] is not None:
            got_set = _as_set(got)
            want_set = _as_set(case["expect_manifests"])
            if got_set != want_set:
                bad.append(
                    f"enumerate_sets({case['given']}) -> {got_set}, "
                    f"expected {want_set}"
                )
    return bad


def run():
    bad = probe_enumerate_sets()
    for line in bad:
        print(line)
    print(f"probe_enumerate_sets: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
