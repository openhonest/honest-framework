"""Conformance fragment for the test_idempotency scenario (honest-test.feature).

Scenario: test_idempotency runs a chain twice and reports not_idempotent when
  results differ.
  Then it runs the chain twice, the second time on a deep copy of the manifest,
  and returns a not_idempotent failure Finding when the two results differ.
  And a chain containing a boundary link is exempt and is not handed here.
  And it returns the failure as a one-element list, or the empty list when the
  chain is idempotent.
  And it performs no I/O of its own.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: the chain
is a real plain function injected as a test input, and the probe calls the real
honest_test.test_idempotency.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import test_idempotency

# A module-level counter the non-idempotent chain reads and increments, so the
# second identical run produces a different result from the first. This is an
# honest injected input, not a mock: a plain function with observable state.
_RUNS = {"n": 0}


def stable_chain(manifest):
    """An idempotent chain: the same manifest in always yields the same result."""
    return {**manifest, "done": True}


def drifting_chain(manifest):
    """A non-idempotent chain: each run folds in a new counter value, so two
    identical runs differ."""
    _RUNS["n"] += 1
    return {**manifest, "run": _RUNS["n"]}


# Each case states the chain it injects, the manifest it runs on, and the exact
# result the scenario fixes: no finding for the idempotent chain, one
# not_idempotent failure for the drifting one.
_CASES = [
    {
        "name": "idempotent chain over a plain manifest",
        "chain": stable_chain,
        "manifest": {"name": "alice", "size": "small"},
        "expect_codes": [],
    },
    {
        "name": "non-idempotent chain over a plain manifest",
        "chain": drifting_chain,
        "manifest": {"name": "alice", "size": "small"},
        "expect_codes": ["not_idempotent"],
    },
]


def probe_test_idempotency():
    """test_idempotency runs a chain twice and returns a single not_idempotent
    failure Finding when the two runs differ, and the empty list when they match."""
    bad = []
    for case in _CASES:
        findings = test_idempotency(chain=case["chain"], test_manifest=case["manifest"])
        got_codes = [f["code"] for f in findings]
        if got_codes != case["expect_codes"]:
            bad.append(
                f"test_idempotency({case['name']}) -> codes {got_codes}, "
                f"expected {case['expect_codes']}"
            )
            continue
        for finding in findings:
            if finding["code"] != "not_idempotent":
                bad.append(
                    f"test_idempotency({case['name']}) emitted code "
                    f"{finding['code']}, expected not_idempotent"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_idempotency({case['name']}) emitted kind "
                    f"{finding['kind']}, expected failure"
                )
    return bad


def run():
    bad = probe_test_idempotency()
    for line in bad:
        print(line)
    print(f"probe_test_idempotency: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
