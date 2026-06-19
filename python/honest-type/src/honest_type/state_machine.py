"""State machines (section 7c): a pure (state, event) -> next_state lookup table.

A state machine is data; transition() is a pure function. States and events are name sets;
the transition table is a binding from (state, event) pairs to next states. No classes, no
mutation - the caller stores the state, the machine only computes the next one.
"""

from honest_type.types import err, fault, ok


class StateMachineError(Exception):
    """A state machine that cannot be built: a transition references an unknown state or
    event, a transition lands on an unknown state, or the initial state is unknown."""


def _names(declaration):
    """The set of names from a states/events declaration: a vocabulary's Set members, or a
    plain set of names used directly."""
    if hasattr(declaration, "get") and "base_types" in declaration:
        names = set()
        for recognizer in declaration["base_types"].values():
            names |= set(recognizer.get("members", frozenset()))
        return frozenset(names)
    return frozenset(declaration)


def state_machine(states, events, transitions, initial, terminal=None):
    """Build a validated state machine (section 7c). Construction fails (StateMachineError)
    when a transition references an unknown state or event, lands on an unknown state, or the
    initial state is not declared - an invalid machine cannot be constructed."""
    state_names = _names(states)
    event_names = _names(events)
    table = dict(transitions)
    for (state, event), next_state in table.items():
        if state not in state_names:
            raise StateMachineError(f"Transition from unknown state '{state}'.")
        if event not in event_names:
            raise StateMachineError(f"Transition on unknown event '{event}'.")
        if next_state not in state_names:
            raise StateMachineError(f"Transition to unknown state '{next_state}'.")
    if initial not in state_names:
        raise StateMachineError(f"Initial state '{initial}' is not a declared state.")
    return {
        "states": state_names,
        "events": event_names,
        "transitions": table,
        "initial": initial,
        "terminal": list(terminal or []),
    }


def transition(machine, current_state, event):
    """Apply one event (section 7c). Returns ok({"state": next}) or err(fault). Pure: the
    machine is stateless; the caller stores the result."""
    if current_state not in machine["states"]:
        return err(fault("invalid_state", f"Unknown state '{current_state}'", "server", {"state": current_state}))
    if event not in machine["events"]:
        return err(fault("invalid_event", f"Unknown event '{event}'", "client", {"event": event}))
    key = (current_state, event)
    if key not in machine["transitions"]:
        return err(
            fault("no_transition", f"No transition for ({current_state}, {event})", "client",
                  {"state": current_state, "event": event})
        )
    return ok({"state": machine["transitions"][key]})
