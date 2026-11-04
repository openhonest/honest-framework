"""Conformance fragment for the verify_purity scenario (honest-test.feature).

Scenario: verify_purity runs a link twice on the same manifest and reports a
  non_deterministic failure when results differ.
  Then it runs the link twice on the same manifest and returns a
  non_deterministic failure Finding when the two results differ, because a pure
  function must return the same output for the same input.
  And it returns the failure as a one-element list, or the empty list when the
  link is pure.
  And it performs no I/O of its own; any effect belongs to the injected link.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks, no
monkeypatching: the link is a real Callable injected as test input. A Manifest is
a plain dict (honest-type's manifest shape). It calls the real
honest_test.verify_purity.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import verify_purity


def pure_link(manifest):
    """A pure link: same input, same output, every call. Mutates nothing."""
    return {**manifest, "seen": True}


# A drifting link: identical input, different output each call. The module-level
# counter makes the second run differ from the first, which is exactly the
# non-determinism verify_purity must catch.
_DRIFT_COUNTER = {"n": 0}


def drifting_link(manifest):
    """A non-deterministic link: its output changes on each identical call."""
    _DRIFT_COUNTER["n"] += 1
    return {**manifest, "call": _DRIFT_COUNTER["n"]}


_CASES = [
    # A pure link run twice on the same manifest agrees with itself: no finding.
    {
        "link": pure_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": [],
    },
    # A drifting link returns a different result the second time: one
    # non_deterministic failure Finding, returned as a one-element list.
    {
        "link": drifting_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": ["non_deterministic"],
    },
]


def probe_verify_purity():
    """verify_purity returns one non_deterministic failure Finding when a link gives different results on identical input, and the empty list when the link is pure."""
    bad = []
    for case in _CASES:
        got = verify_purity(case["link"], case["test_manifest"])
        if not isinstance(got, list):
            bad.append(
                f"verify_purity({case['link'].__name__}) -> {got!r}, "
                f"expected a list"
            )
            continue
        got_codes = [f["code"] for f in got]
        if got_codes != case["expect_codes"]:
            bad.append(
                f"verify_purity({case['link'].__name__}) produced codes "
                f"{got_codes}, expected {case['expect_codes']}"
            )
            continue
        # For the failing case, pin the grade too: a non_deterministic finding
        # is a failure, never a warning or rejection.
        for finding in got:
            if finding["kind"] != "failure":
                bad.append(
                    f"verify_purity({case['link'].__name__}) finding "
                    f"{finding['code']} has kind {finding['kind']!r}, "
                    f"expected 'failure'"
                )
    return bad


def run():
    bad = probe_verify_purity()
    for line in bad:
        print(line)
    print(f"probe_verify_purity: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
