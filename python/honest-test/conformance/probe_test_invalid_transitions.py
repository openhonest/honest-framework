"""honest-test conformance: test_invalid_transitions — every undeclared pair is refused.

The spec (§5.2): for each state and each event with no declared transition, apply the event
and emit an invalid_transition_accepted failure when the result is not a no_transition fault.
This probe builds a tiny machine with exactly one undeclared (valid-state, valid-event) pair
and injects run_transition two ways: a correct one that faults no_transition on that pair,
which must yield no findings, and one that accepts the pair, which must yield one
invalid_transition_accepted failure.

No classes, no mocks. It calls the real honest_test.test_invalid_transitions.
"""

from honest_test import test_invalid_transitions


def _machine():
    # Three of the four (state, event) pairs are declared; ("unlocked", "coin") is not.
    return {
        "states": ["locked", "unlocked"],
        "events": ["coin", "push"],
        "transitions": {
            ("locked", "coin"): "unlocked",
            ("locked", "push"): "locked",
            ("unlocked", "push"): "locked",
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


def _accepts_undeclared(machine, state, event):
    """Buggy: an undeclared (valid-state, valid-event) pair is accepted, not refused."""
    if state not in machine["states"]:
        return {"code": "invalid_state"}
    if event not in machine["events"]:
        return {"code": "invalid_event"}
    key = (state, event)
    if key in machine["transitions"]:
        return {"state": machine["transitions"][key]}
    return {"state": state}


def probe_test_invalid_transitions():
    bad = []
    machine = _machine()

    clean = test_invalid_transitions(machine, _correct_transition)
    if clean != []:
        bad.append(f"every undeclared pair faulting no_transition should yield no findings, got {clean!r}")

    flagged = test_invalid_transitions(machine, _accepts_undeclared)
    undeclared = len(machine["states"]) * len(machine["events"]) - len(machine["transitions"])
    if len(flagged) != undeclared:
        bad.append(f"accepting an undeclared pair should yield one finding per undeclared pair ({undeclared}), got {len(flagged)}")
    for f in flagged:
        if f.get("code") != "invalid_transition_accepted":
            bad.append(f"an accepted undeclared pair should carry code 'invalid_transition_accepted', got {f.get('code')!r}")
        if f.get("kind") != "failure":
            bad.append(f"an invalid_transition_accepted finding should be a failure, got kind {f.get('kind')!r}")
    return bad


def run():
    messages = probe_test_invalid_transitions()
    if messages:
        print(f"FAIL HTEST-probe [test_invalid_transitions]: {messages}")
    print(f"test_invalid_transitions: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
