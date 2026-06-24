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


class Fault(TypedDict, total=False):
    """A processing error. Data, not an exception (section 11.2). `code`, `message`, and `category`
    ('client'|'server') are always present — a fault without a category is itself a server error.
    `link`, `input`, and `results` are the named chain-fault fields (the link that produced it, the
    manifest passed to it, and — for validation_failed — every accumulated result), present only when
    set; `detail` carries any other fault-specific context (a rejected token, a state machine's state
    and event, the boundary rejections)."""

    code: str
    message: str
    category: str
    detail: dict[str, Any] | None
    link: str
    input: Any
    results: list


def ticket(type_name: str, value: str) -> Ticket:
    return {"type": type_name, "value": value}


def rejection(token, reason: str, detail=None) -> Rejection:
    return {"token": token, "reason": reason, "detail": detail}


def fault(code: str, message: str, category: str, detail=None, link=None, input=None, results=None) -> Fault:
    """A fault (section 11.2). code/message/category always present; the named chain fields
    link/input/results are added only when supplied; detail carries any other context."""
    out: Fault = {"code": code, "message": message, "category": category, "detail": detail}
    if link is not None:
        out["link"] = link
    if input is not None:
        out["input"] = input
    if results is not None:
        out["results"] = results
    return out


def ok(manifest) -> dict:
    """A successful link Result (section 10.1): {"ok": manifest}."""
    return {"ok": manifest}


def err(fault_data: Fault) -> dict:
    """A failed link Result (section 10.1): {"err": fault_data}."""
    return {"err": fault_data}
