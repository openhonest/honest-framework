"""The three state-machine checks (spec section 5): every declared transition is
correct, every undeclared pair is refused, and every adversarial neighbor of a state or
event is rejected. Each is pure: it reads the machine as data and runs the injected
transition, returning a list of Findings.
"""

from itertools import product

from honest_test._util import _choose, _read_or
from honest_test.generate import adversarial_neighbors

_finding = lambda kind, code, message, location: {"kind": kind, "code": code, "message": message, "location": location}


def test_valid_transitions(machine, run_transition):
    """Exhaustively test every declared transition (section 5.1): apply each (state, event)
    and fault transition_incorrect when the result is not ok of the expected next state,
    driving transition coverage to 100 by construction."""
    def _check(item):
        (state, event), expected = item
        result = run_transition(machine, state, event)
        correct = _read_or(result, "state", None) == expected
        return _choose(
            correct,
            [],
            [_finding("failure", "transition_incorrect", f"transition ({state!r}, {event!r}) did not reach {expected!r}", "")],
        )

    return [found for item in machine["transitions"].items() for found in _check(item)]


def test_invalid_transitions(machine, run_transition):
    """Exhaustively test every (state, event) pair the table does not declare (section 5.2):
    apply the event and fault invalid_transition_accepted when the result is not a
    no_transition fault, because an undeclared pair must be refused."""
    pairs = product(machine["states"], machine["events"])
    undeclared = filter(lambda pair: pair not in machine["transitions"], pairs)

    def _check(pair):
        state, event = pair
        result = run_transition(machine, state, event)
        refused = _read_or(result, "code", "") == "no_transition"
        return _choose(
            refused,
            [],
            [_finding("failure", "invalid_transition_accepted", f"undeclared pair ({state!r}, {event!r}) was accepted instead of faulting no_transition", "")],
        )

    return [found for pair in undeclared for found in _check(pair)]


def test_adversarial_state_machine(machine, run_transition):
    """Test adversarial neighbors of the machine's states and events (section 5.3): each
    neighbor of a state fed the first valid event must fault invalid_state, and each
    neighbor of an event fed the first valid state must fault invalid_event."""
    first_event = machine["events"][0]
    first_state = machine["states"][0]

    def _state_failures():
        out = []
        for state in machine["states"]:
            for neighbor in adversarial_neighbors(state):
                result = run_transition(machine, neighbor, first_event)
                rejected = _read_or(result, "code", "") == "invalid_state"
                out.extend(_choose(rejected, [], [_finding("failure", "invalid_state", f"adversarial neighbor of state {state!r} was accepted", "")]))
        return out

    def _event_failures():
        out = []
        for event in machine["events"]:
            for neighbor in adversarial_neighbors(event):
                result = run_transition(machine, first_state, neighbor)
                rejected = _read_or(result, "code", "") == "invalid_event"
                out.extend(_choose(rejected, [], [_finding("failure", "invalid_event", f"adversarial neighbor of event {event!r} was accepted", "")]))
        return out

    return _state_failures() + _event_failures()
