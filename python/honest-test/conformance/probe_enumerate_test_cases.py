"""Conformance fragment for the enumerate_test_cases scenario (honest-test.feature).

Scenario: enumerate_test_cases builds the input manifests a link accepts for
chain-contract testing.
  Given accepts: Vocabulary and binding: Binding
  When enumerate_test_cases is called
  Then it enumerates the vocabulary the way enumerate_sets does and resolves each
  combination into a manifest through the binding, so each case is a ready input
  for the link under test.
  And it returns the list of manifests, reading no world and returning pure data.

enumerate_test_cases is the binding-aware sibling of enumerate_sets. The one thing
that distinguishes it: the manifest keys are the BINDING's slot names, not the
vocabulary's type names. So when the binding maps type "color" -> slot "hue", the
manifests are keyed "hue", not "color". Every case below pins that renaming with a
literal expected manifest, so a stub returning [] (or one that forgets to rename)
cannot pass.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_type.vocabulary and honest_type.binding to build the inputs and the
real honest_test.enumerate_test_cases to produce the output.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import binding, vocabulary

from honest_test import enumerate_test_cases

# 150 distinct members for the scenario-sibling 5 x 150 x 4 = 3000 count literal.
_B150 = {f"b{i}" for i in range(150)}

_CASES = [
    # Two Sets, with a binding that renames each type to a different slot. The
    # Cartesian product is the four manifests below, written out by hand and keyed
    # by the SLOT names ("hue", "dimension"), never the type names ("color",
    # "size"). A stub returning [] cannot pass, and one that keeps the type names
    # as keys cannot pass either.
    {
        "accepts": {"color": {"red", "green"}, "size": {"small", "large"}},
        "binding": {"color": "hue", "size": "dimension"},
        "expect_count": 4,
        "expect_manifests": [
            {"hue": "red", "dimension": "small"},
            {"hue": "red", "dimension": "large"},
            {"hue": "green", "dimension": "small"},
            {"hue": "green", "dimension": "large"},
        ],
    },
    # A singleton Set yields exactly one manifest, keyed by its renamed slot.
    {
        "accepts": {"only": {"x"}},
        "binding": {"only": "payload"},
        "expect_count": 1,
        "expect_manifests": [{"payload": "x"}],
    },
    # The count literal shared with enumerate_sets: three Sets of 5, 150 and 4
    # members yield all 3,000 cases, no sampling, with every type renamed to a
    # slot. Content is not spelled out; the count is.
    {
        "accepts": {
            "a": {"a0", "a1", "a2", "a3", "a4"},
            "b": _B150,
            "c": {"c0", "c1", "c2", "c3"},
        },
        "binding": {"a": "slot_a", "b": "slot_b", "c": "slot_c"},
        "expect_count": 3000,
        "expect_manifests": None,
    },
]


def _as_set(manifests):
    """A list of manifest dicts as a hashable set, so order is not asserted."""
    return {frozenset(m.items()) for m in manifests}


def probe_enumerate_test_cases():
    """enumerate_test_cases yields the full Cartesian product of every Set member, one manifest per combination, each manifest keyed by the binding's slot names rather than the vocabulary's type names."""
    bad = []
    for case in _CASES:
        vocab = vocabulary(case["accepts"])
        bind = binding(case["binding"])
        got = enumerate_test_cases(vocab, bind)
        if len(got) != case["expect_count"]:
            bad.append(
                f"enumerate_test_cases({case['accepts']}, {case['binding']}) "
                f"produced {len(got)} manifests, expected {case['expect_count']}"
            )
            continue
        if case["expect_manifests"] is not None:
            got_set = _as_set(got)
            want_set = _as_set(case["expect_manifests"])
            if got_set != want_set:
                bad.append(
                    f"enumerate_test_cases({case['accepts']}, {case['binding']}) "
                    f"-> {got_set}, expected {want_set}"
                )
    return bad


def run():
    bad = probe_enumerate_test_cases()
    for line in bad:
        print(line)
    print(f"probe_enumerate_test_cases: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
