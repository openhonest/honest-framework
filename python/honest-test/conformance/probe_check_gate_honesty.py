"""Conformance fragment for the check_gate_honesty scenario (honest-test.feature).

Scenario: check_gate_honesty requires every gate to name a bound proof-of-failure test.
  Then it returns a gate_unverified rejection Finding for a gate with no proof,
  because a gate whose failing arm has never executed carries no information when
  the run is green.
  And it returns a gate_proof_unbound rejection Finding for a proof that asserts
  only that some exception was raised rather than binding the specific failure.
  And it returns one rejection per dishonest gate, empty when every gate is proven.

Cases are data; one pure probe feeds them to the real honest_test.check_gate_honesty
and returns a list of failure strings (empty when every case holds). No classes, no
mocks: plain gate dicts in, Finding dicts out. A Gate is
{"name", "location", "proof": {...} or None}; a Proof is
{"location", "binds_failure": True/False}; proof=None is the NOTHING absence case.

Own fragment file so the other scenarios' fragments never collide with it.
"""

from honest_test import check_gate_honesty


def _gate(name, location, proof):
    return {"name": name, "location": location, "proof": proof}


def _proof(location, binds_failure):
    return {"location": location, "binds_failure": binds_failure}


_CASES = [
    # (a) a gate with a bound proof -> no finding, the honest gate.
    {
        "gates": [
            _gate("fixture-guard", "conftest.py:3", _proof("test_guard.py:10", True)),
        ],
        "expect_codes": [],
    },
    # (b) a gate with no proof (NOTHING / None) -> one gate_unverified rejection.
    {
        "gates": [
            _gate("session-guard", "conftest.py:7", None),
        ],
        "expect_codes": ["gate_unverified"],
    },
    # (c) a gate whose proof does not bind the failure -> one gate_proof_unbound.
    {
        "gates": [
            _gate("marker-select", "conftest.py:9", _proof("test_marker.py:4", False)),
        ],
        "expect_codes": ["gate_proof_unbound"],
    },
    # (d) a mixed list: three dishonest gates and two honest ones. One rejection
    # per dishonest gate, honest gates contribute none. Count and codes pinned.
    {
        "gates": [
            _gate("g1", "a.py:1", _proof("ta.py:1", True)),    # honest
            _gate("g2", "b.py:2", None),                       # gate_unverified
            _gate("g3", "c.py:3", _proof("tc.py:3", False)),   # gate_proof_unbound
            _gate("g4", "d.py:4", _proof("td.py:4", True)),    # honest
            _gate("g5", "e.py:5", None),                       # gate_unverified
        ],
        "expect_codes": ["gate_unverified", "gate_proof_unbound", "gate_unverified"],
    },
]


def probe_check_gate_honesty():
    """check_gate_honesty rejects a proofless gate as gate_unverified and an unbound-proof gate as gate_proof_unbound, one rejection per dishonest gate, empty when every gate is proven."""
    bad = []
    for case in _CASES:
        got = check_gate_honesty(case["gates"])
        got_codes = sorted(f["code"] for f in got)
        want_codes = sorted(case["expect_codes"])
        if got_codes != want_codes:
            bad.append(
                f"check_gate_honesty({case['gates']}) -> codes {got_codes}, "
                f"expected {want_codes}"
            )
            continue
        for finding in got:
            if finding["kind"] != "rejection":
                bad.append(
                    f"check_gate_honesty({case['gates']}) finding {finding['code']} "
                    f"had kind {finding['kind']!r}, expected 'rejection'"
                )
    return bad


def run():
    bad = probe_check_gate_honesty()
    for line in bad:
        print(line)
    print(f"probe_check_gate_honesty: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
