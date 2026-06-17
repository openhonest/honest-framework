"""Manifest — fully resolved binding result. slot → value dict + raw tickets."""
from __future__ import annotations

from honest_type.types import Fault, Manifest, Ticket


def emit_manifest(tickets: list[Ticket]) -> Manifest:
    """Pure. Fold tickets into slots by their `slot` field.

    Tickets with slot="" are kept in the tickets list but not added to
    slots. If two tickets map to the same slot, the later one wins (caller
    decides whether that's a bug; honest-check flags it).
    """
    slots: dict[str, str] = {}
    for t in tickets:
        if t["slot"]:
            slots[t["slot"]] = t["value"]
    return Manifest(slots=dict(slots), tickets=list(tickets))


def emit_fault(code: str, category: str, message: str) -> Fault:
    """Pure constructor. Exceptions live only at the HTTP boundary; faults
    are data.
    """
    return Fault(code=code, category=category, message=message)
