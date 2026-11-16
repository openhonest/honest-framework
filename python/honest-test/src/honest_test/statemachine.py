"""State-machine exhaustive testing (spec section 5).

Every check takes a live StateMachine and honest-type's transition passed in as run_transition,
so it runs the real transition function and performs no I/O of its own. Faults travel as Finding
records.
"""

from honest_type import is_fault

from honest_test._util import _pick, _read_or
from honest_test.generators import adversarial_neighbors
from honest_test.support import _finding


def test_valid_transitions(machine, run_transition):
    """Exhaustively test every declared transition (spec section 5.1): apply each (state, event)
    and report transition_incorrect when the result is not the bare {state: next} of the expected
    next state. transition returns a bare manifest or a bare Fault, no envelope (honest-type 12.1)."""
    findings = []
    for (state, event), next_state in machine["transitions"].items():
        result = run_transition(machine, state, event)
        _pick(
            result != {"state": next_state},
            lambda: findings.append(_finding(
                "failure", "transition_incorrect",
                f"({state}, {event}) expected next state {next_state!r}, got {result!r}")),
            lambda: None,
        )
    return findings


def test_invalid_transitions(machine, run_transition):
    """Exhaustively test every (state, event) pair the table does not declare (spec section 5.2):
    an undeclared pair must fault no_transition, or it is invalid_transition_accepted."""
    findings = []
    pairs = ((state, event)
             for state in sorted(machine["states"])
             for event in sorted(machine["events"]))
    undeclared = filter(lambda pe: pe not in machine["transitions"], pairs)
    for (state, event) in undeclared:
        result = run_transition(machine, state, event)
        _pick(
            is_fault(result) and _read_or(result, "code", None) == "no_transition",
            lambda: None,
            lambda: findings.append(_finding(
                "failure", "invalid_transition_accepted",
                f"undeclared pair ({state}, {event}) was accepted instead of faulting no_transition")),
        )
    return findings


def test_adversarial_state_machine(machine, run_transition):
    """Test adversarial neighbors of every state and event (spec section 5.3): a state neighbor
    accepted with the first valid event is invalid_state; an event neighbor accepted with the
    first valid state is invalid_event."""
    findings = []
    first_event = sorted(machine["events"])[0]
    first_state = sorted(machine["states"])[0]
    for state in sorted(machine["states"]):
        for neighbor in adversarial_neighbors(state):
            _pick(
                is_fault(run_transition(machine, neighbor, first_event)),
                lambda: None,
                lambda: findings.append(_finding(
                    "failure", "invalid_state",
                    f"adversarial state neighbor {neighbor!r} was accepted")),
            )
    for event in sorted(machine["events"]):
        for neighbor in adversarial_neighbors(event):
            _pick(
                is_fault(run_transition(machine, first_state, neighbor)),
                lambda: None,
                lambda: findings.append(_finding(
                    "failure", "invalid_event",
                    f"adversarial event neighbor {neighbor!r} was accepted")),
            )
    return findings
