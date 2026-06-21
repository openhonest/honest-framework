"""State machine testing (section 5.1-5.3): valid, invalid, and adversarial transitions.

Auto-generated from a state machine's declaration. test_valid checks the declared table;
test_invalid checks that undeclared (state, event) pairs fault with no_transition; test_
adversarial checks that near-miss state/event tokens are rejected - a neighbour that is
accepted is an overlap (two states or events too similar). Each returns findings (data).

Deferred: section 5.4 (state invariants) and 5.6 (K-step sequences) need a field-rich state
model the name-based primitive does not carry; section 5.5 (TOCTOU) needs honest-persist.
"""

from honest_type import ok, target_next, transition

from honest_test.adversarial import adversarial_neighbours


def _finding(code, detail):
    return {"code": code, "detail": detail}


def _is_err(result, code):
    return "err" in result and result["err"]["code"] == code


def _first(names):
    for name in sorted(names):
        return name
    return None


def test_valid_transitions(machine):
    """Every declared (state, event) -> next must produce ok({state: next}) (section 5.1)."""
    findings = []
    for (state, event), target in machine["transitions"].items():
        if transition(machine, state, event) != ok({"state": target_next(target)}):
            findings.append(_finding("transition_incorrect", {"state": state, "event": event}))
    return findings


def test_invalid_transitions(machine):
    """Every (state, event) pair not in the table must fault no_transition (section 5.2)."""
    findings = []
    for state in machine["states"]:
        for event in machine["events"]:
            if (state, event) in machine["transitions"]:
                continue
            if not _is_err(transition(machine, state, event), "no_transition"):
                findings.append(_finding("invalid_transition_accepted", {"state": state, "event": event}))
    return findings


def test_adversarial_transitions(machine):
    """Near-miss state and event tokens must be rejected (section 5.3). A neighbour that is
    accepted reveals an overlap. The empty-machine edge is skipped."""
    findings = []
    valid_event = _first(machine["events"])
    valid_state = _first(machine["states"])
    if valid_event is not None:
        for state in machine["states"]:
            for neighbour in adversarial_neighbours(state):
                if not _is_err(transition(machine, neighbour, valid_event), "invalid_state"):
                    findings.append(_finding("adversarial_state_accepted", {"neighbour": neighbour[:24]}))
    if valid_state is not None:
        for event in machine["events"]:
            for neighbour in adversarial_neighbours(event):
                if not _is_err(transition(machine, valid_state, neighbour), "invalid_event"):
                    findings.append(_finding("adversarial_event_accepted", {"neighbour": neighbour[:24]}))
    return findings
