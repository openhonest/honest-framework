"""honest-test conformance: test_adversarial_state_machine — neighbors must be rejected.

The spec (§5.3): for each state, feed each adversarial neighbor of that state the first valid
event and emit an invalid_state failure when the neighbor is accepted; for each event, feed
the first valid state each adversarial neighbor and emit an invalid_event failure when the
neighbor is accepted. The neighbors come from adversarial_neighbors. This probe builds a tiny
machine and injects run_transition two ways: a correct one that faults invalid_state /
invalid_event for any unknown state / event, which must yield no findings, and one that
accepts every unknown token, which must yield both an invalid_state and an invalid_event
failure.

No classes, no mocks. It calls the real honest_test.test_adversarial_state_machine.
"""

from honest_test import test_adversarial_state_machine


def _machine():
    return {
        "states": ["locked", "unlocked"],
        "events": ["coin", "push"],
        "transitions": {
            ("locked", "coin"): "unlocked",
            ("locked", "push"): "locked",
            ("unlocked", "push"): "locked",
            ("unlocked", "coin"): "unlocked",
        },
        "initial": "locked",
        "terminal": [],
    }


def _correct_transition(machine, state, event):
    if state not in machine["states"]:
        return {"code": "invalid_state"}
    if event not in machine["events"]:
        return {"code": "invalid_event"}
    key = (state, event)
    if key in machine["transitions"]:
        return {"state": machine["transitions"][key]}
    return {"code": "no_transition"}


def _accepts_everything(machine, state, event):
    """Buggy: an unknown state or event is accepted instead of faulting."""
    key = (state, event)
    if key in machine["transitions"]:
        return {"state": machine["transitions"][key]}
    return {"state": machine["states"][0]}


def probe_test_adversarial_state_machine():
    bad = []
    machine = _machine()

    clean = test_adversarial_state_machine(machine, _correct_transition)
    if clean != []:
        bad.append(f"rejecting every adversarial neighbor should yield no findings, got {len(clean)} finding(s)")

    flagged = test_adversarial_state_machine(machine, _accepts_everything)
    if not flagged:
        bad.append("accepting adversarial neighbors should yield findings, got none")
    codes = {f.get("code") for f in flagged}
    if not codes <= {"invalid_state", "invalid_event"}:
        bad.append(f"adversarial findings should be invalid_state or invalid_event, got {codes}")
    if "invalid_state" not in codes:
        bad.append("an accepted adversarial state neighbor should yield an invalid_state failure")
    if "invalid_event" not in codes:
        bad.append("an accepted adversarial event neighbor should yield an invalid_event failure")
    for f in flagged:
        if f.get("kind") != "failure":
            bad.append(f"an adversarial finding should be a failure, got kind {f.get('kind')!r}")
            break
    return bad


def run():
    messages = probe_test_adversarial_state_machine()
    if messages:
        print(f"FAIL HTEST-probe [test_adversarial_state_machine]: {messages}")
    print(f"test_adversarial_state_machine: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
