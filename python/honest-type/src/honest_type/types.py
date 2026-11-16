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
    """A processing error. Data, not an exception (sections 11.2, 13.2). Every field is always present.
    code/message/category say what went wrong and who is responsible ('client'|'server'); a fault
    without a category is itself a server error. results holds every accumulated result for a
    validate_all fault and is [] otherwise. detail carries the fault's enumerable facts as structured
    data a test or caller reads without parsing the message (the failing link, a dispatch fault's
    accepted keys and arriving value, a rejected token, a state machine's state and event) and is {}
    when there is none."""

    code: str
    message: str
    category: str
    results: list
    detail: dict[str, Any]


def ticket(type_name: str, value: str) -> Ticket:
    return {"type": type_name, "value": value}


def rejection(token, reason: str, detail=None) -> Rejection:
    return {"token": token, "reason": reason, "detail": detail}


def fault(code: str, message: str, category: str, results: list, detail: dict) -> Fault:
    """A fault (sections 11.2, 13.2). Every field is passed explicitly: results is [] unless this is a
    validate_all fault, detail is {} unless there is structured context. Nothing is defaulted, so a
    caller can never omit a field by accident and manufacture an untested input region."""
    return {"code": code, "message": message, "category": category, "results": results, "detail": detail}


def is_fault(value) -> bool:
    """The Fault recognizer (section 12.1): true for a Fault-shaped value, false for a manifest.

    A link returns its value on success or a Fault on failure — a bare union, no envelope (sections
    12.1, 12.3). The chain executor tells the two apart by this predicate: a Fault carries a `code`,
    a manifest never does. It trusts the contract that both members of the union are dicts, so it reads
    the key directly without re-testing the type in the interior."""
    return "code" in value


def ok(manifest) -> dict:
    """A success-wrapping Result (section 10.1): {"ok": manifest}. honest-type's own chain model no
    longer wraps — a link returns its value bare and the executor recognizes a Fault with is_fault
    (section 12.1). ok() and err() stay as general-purpose Result constructors for modules that build
    their own pass/fail Result (honest-test's value oracle and state-machine checks among them)."""
    return {"ok": manifest}


def err(fault_data: Fault) -> dict:
    """A failure-wrapping Result (section 10.1): {"err": fault_data}. See ok() — retained for the
    same reason; honest-type's chain model returns a bare Fault instead."""
    return {"err": fault_data}
