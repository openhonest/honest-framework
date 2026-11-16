"""State machines (section 7c): a pure (state, event) -> next_state lookup table.

A state machine is data; transition() is a pure function. States and events are name sets;
the transition table is a binding from (state, event) pairs to next states. No classes, no
mutation - the caller stores the state, the machine only computes the next one.
"""

from types import MappingProxyType

from honest_type._util import _choose, _pick, _read_or
from honest_type.types import fault


def _names(declaration):
    """The set of names from a states/events declaration: a vocabulary's Set members, or a
    plain set of names used directly."""
    return _pick(
        hasattr(declaration, "get") and "base_types" in declaration,
        lambda: frozenset().union(*(
            set(_read_or(recognizer, "members", frozenset()))
            for recognizer in declaration["base_types"].values()
        )),
        lambda: frozenset(declaration),
    )


def _one_transition_faults(state_event_target, state_names, event_names):
    """The construction faults of one (state, event) -> target transition, in check order: an
    unknown source state, an unknown event, an unknown target state. Each candidate is a fault
    or None, and only the real faults survive. Pure."""
    (state, event), target = state_event_target
    candidates = [
        _choose(state not in state_names,
                fault("unknown_state_in_transition", f"Transition from unknown state '{state}'.",
                      "server", [], {"state": state}), None),
        _choose(event not in event_names,
                fault("unknown_event_in_transition", f"Transition on unknown event '{event}'.",
                      "server", [], {"event": event}), None),
        _choose(target not in state_names,
                fault("unknown_target_state", f"Transition to unknown state '{target}'.",
                      "server", [], {"target": target}), None),
    ]
    return list(filter(None, candidates))


def _state_machine_fault(table, state_names, event_names, initial):
    """The first construction fault in a machine's transitions (in table order) or its initial
    state, or None when the machine is valid. Pure."""
    transition_faults = [
        found
        for state_event_target in table.items()
        for found in _one_transition_faults(state_event_target, state_names, event_names)
    ]
    initial_faults = _choose(
        initial not in state_names,
        [fault("unknown_initial_state", f"Initial state '{initial}' is not a declared state.",
               "server", [], {"initial": initial})],
        [],
    )
    return next(iter(transition_faults + initial_faults), None)


def state_machine(states, events, transitions, initial, terminal=None):
    """Build a validated state machine (section 7c). Returns the machine, or a Fault value when a
    transition references an unknown state or event, lands on an unknown state, or the initial state
    is not declared (section 11.2) - an invalid machine comes back as data, never a raise."""
    state_names = _names(states)
    event_names = _names(events)
    table = dict(transitions)
    found = _state_machine_fault(table, state_names, event_names, initial)
    return _pick(
        found is not None,
        lambda: found,
        lambda: MappingProxyType({
            "states": state_names,
            "events": event_names,
            "transitions": MappingProxyType(table),
            "initial": initial,
            "terminal": tuple(terminal or []),
        }),
    )


def _transition_fault(machine, current_state, event):
    """The first fault applying one event to a state would hit: an unknown current state, an
    unknown event, or no declared transition for the pair. None when the move is legal. Pure."""
    candidates = [
        _choose(current_state not in machine["states"],
                fault("invalid_state", f"Unknown state '{current_state}'", "server", [], {"state": current_state}), None),
        _choose(event not in machine["events"],
                fault("invalid_event", f"Unknown event '{event}'", "client", [], {"event": event}), None),
        _choose((current_state, event) not in machine["transitions"],
                fault("no_transition", f"No transition for ({current_state}, {event})", "client",
                      [], {"state": current_state, "event": event}), None),
    ]
    return next(filter(None, candidates), None)


def transition(machine, current_state, event):
    """Apply one event (section 7c). Returns a bare {"state": next} on success or a bare Fault on
    failure (section 12.1) — no envelope. Pure: the machine is stateless; the caller stores the
    result. The faulting rows are the terminal entries of this (state, event) dispatch (section 13.7)."""
    found = _transition_fault(machine, current_state, event)
    return _pick(
        found is not None,
        lambda: found,
        lambda: {"state": machine["transitions"][(current_state, event)]},
    )
