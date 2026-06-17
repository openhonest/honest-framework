"""Pure state machine."""
from __future__ import annotations

from typing import TypedDict


class StateMachine(TypedDict):
    name: str
    states: frozenset[str]
    events: frozenset[str]
    transitions: dict[tuple[str, str], str]   # (state, event) -> next_state
    initial: str
    terminal: frozenset[str]


class TransitionResult(TypedDict):
    ok_state: str
    err_code: str
    err_category: str
    err_message: str


def state_machine(
    name: str,
    states: list[str],
    events: list[str],
    transitions: dict[tuple[str, str], str],
    initial: str,
    terminal: list[str] | None = None,
) -> StateMachine:
    return StateMachine(
        name=name,
        states=frozenset(states),
        events=frozenset(events),
        transitions=dict(transitions),
        initial=initial,
        terminal=frozenset(terminal or []),
    )


def validate_state(machine: StateMachine, current: str) -> bool:
    return current in machine["states"]


def validate_event(machine: StateMachine, event: str) -> bool:
    return event in machine["events"]


def is_terminal(machine: StateMachine, current: str) -> bool:
    return current in machine["terminal"]


def lookup_transition(
    machine: StateMachine, current: str, event: str,
) -> str | None:
    return machine["transitions"].get((current, event))


def transition(
    machine: StateMachine, current: str, event: str,
) -> TransitionResult:
    if not validate_state(machine, current):
        return TransitionResult(
            ok_state="", err_code="invalid_state",
            err_category="client",
            err_message=f"{current!r} not in {list(machine['states'])}",
        )
    if not validate_event(machine, event):
        return TransitionResult(
            ok_state="", err_code="invalid_event",
            err_category="client",
            err_message=f"{event!r} not in {list(machine['events'])}",
        )
    if is_terminal(machine, current):
        return TransitionResult(
            ok_state="", err_code="terminal_state",
            err_category="client",
            err_message=f"{current!r} is terminal",
        )
    nxt = lookup_transition(machine, current, event)
    if nxt is None:
        return TransitionResult(
            ok_state="", err_code="no_transition",
            err_category="client",
            err_message=f"no transition ({current!r}, {event!r})",
        )
    return TransitionResult(
        ok_state=nxt, err_code="", err_category="", err_message="",
    )


# Alias.
advance = transition
