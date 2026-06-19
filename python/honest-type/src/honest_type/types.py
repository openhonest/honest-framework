"""honest-type data shapes (section 7). Plain data; pure constructors; no behaviour.

A ticket is the result of classifying one token. A rejection is a token that could not
be classified or bound — data, never an exception. A fault is a processing error (a
server bug) — also data; exceptions only at the HTTP boundary.
"""

from typing import Any, TypedDict


class Ticket(TypedDict):
    """The result of classifying a single token (section 7)."""

    type: str
    value: str


class Rejection(TypedDict):
    """A token that could not be classified or bound, or a missing required slot."""

    token: str | None
    reason: str  # unrecognized | reserved_word | unbound_type | duplicate_slot | missing_required | empty_token | null_token
    detail: str | None


class Fault(TypedDict):
    """A processing error. Data, not an exception. `category` ('client'|'server') is
    required (section 11.2) — a fault without a category is itself a server error."""

    code: str
    message: str
    category: str
    detail: dict[str, Any] | None


def ticket(type_name: str, value: str) -> Ticket:
    return {"type": type_name, "value": value}


def rejection(token, reason: str, detail=None) -> Rejection:
    return {"token": token, "reason": reason, "detail": detail}


def fault(code: str, message: str, category: str, detail=None) -> Fault:
    return {"code": code, "message": message, "category": category, "detail": detail}
