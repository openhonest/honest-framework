"""honest-test conformance: check_gate_honesty rejects a gate with no proof or an unbound proof.

Spec section 4.9, feature "check_gate_honesty rejects a gate with no proof or an unbound
proof", .hd check_gate_honesty, Gate and Proof. Every declared gate must name a
proof-of-failure test that supplies a known-bad input and requires the specific failure.
check_gate_honesty returns a gate_unverified rejection for a gate with no proof, and a
gate_proof_unbound rejection for a proof that asserts only that some exception was raised
rather than binding the specific failure. Empty when every gate is proven.

No classes, no mocks. The gates are real Gate values (honest-test's own record) built
here. A gate's proof is a Proof record or NOTHING, the explicit absence arm; binds_failure
is true when the proof requires the specific failure, false when it catches any exception.
A Finding carries a "code" and a "kind".
"""

from honest_test import NOTHING, check_gate_honesty

_PROVEN_GATE = {
    "name": "db_reachable",
    "location": "gates.py:10",
    "proof": {"location": "test_gates.py:5", "binds_failure": True},
}

_UNVERIFIED_GATE = {
    "name": "session_guard",
    "location": "gates.py:20",
    "proof": NOTHING,
}

_UNBOUND_GATE = {
    "name": "marker_selected",
    "location": "gates.py:30",
    "proof": {"location": "test_gates.py:9", "binds_failure": False},
}


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def probe_check_gate_honesty():
    bad = []

    proven = check_gate_honesty([_PROVEN_GATE])
    if proven != []:
        bad.append(f"a gate with a failure-binding proof should yield no finding, got {proven!r}")

    unverified = check_gate_honesty([_UNVERIFIED_GATE])
    if _codes(unverified) != ["gate_unverified"]:
        bad.append(f"a gate with no proof should yield one gate_unverified rejection, got {unverified!r}")
    elif unverified[0].get("kind") != "rejection":
        bad.append(f"a gate_unverified finding must be graded a rejection, got kind {unverified[0].get('kind')!r}")

    unbound = check_gate_honesty([_UNBOUND_GATE])
    if _codes(unbound) != ["gate_proof_unbound"]:
        bad.append(
            f"a proof that does not bind the specific failure should yield one "
            f"gate_proof_unbound rejection, got {unbound!r}"
        )
    elif unbound[0].get("kind") != "rejection":
        bad.append(f"a gate_proof_unbound finding must be graded a rejection, got kind {unbound[0].get('kind')!r}")

    both = check_gate_honesty([_UNVERIFIED_GATE, _UNBOUND_GATE])
    if set(_codes(both)) != {"gate_unverified", "gate_proof_unbound"}:
        bad.append(f"two dishonest gates should each yield their rejection, got {both!r}")

    return bad


def run():
    messages = probe_check_gate_honesty()
    for message in messages:
        print(f"FAIL HT-probe [check_gate_honesty]: {message}")
    print(f"check_gate_honesty: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
