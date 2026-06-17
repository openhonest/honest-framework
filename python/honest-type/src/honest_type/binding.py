"""Binding — map type names to slot names, resolve tickets to slots.

A Binding is a plain dict of rules: `{"email": "user_email", "age": "user_age"}`.
resolve_bindings takes a list of tickets and returns a new list where
each matching ticket has its `slot` field populated.
"""
from __future__ import annotations

from honest_type.types import Binding, Ticket


def binding(rules: dict[str, str]) -> Binding:
    """Pure constructor."""
    return Binding(rules=dict(rules))


def resolve_bindings(tickets: list[Ticket], b: Binding) -> list[Ticket]:
    """Pure. Return new tickets with `slot` populated from the binding.
    Tickets whose type has no rule get slot="" preserved.
    """
    return [
        Ticket(
            type=t["type"],
            value=t["value"],
            slot=b["rules"].get(t["type"], t.get("slot", "")),
        )
        for t in tickets
    ]
