"""The shared Result / Fault shape, as data.

honest-design sits below honest-type in the build order (design -> parse only), so it cannot import
honest-type's Result. Faults are data, and the {ok}/{err} shape is a convention, not a dependency:
this module emits that same shape directly. A fault carries code/message/category/detail; category
is "client" (the .hd file is malformed) or "server" (a reader invariant broke).
"""

from typing import TypedDict


class Fault(TypedDict):
    code: str
    message: str
    category: str
    detail: dict


class Result(TypedDict, total=False):
    ok: object
    err: Fault


def fault(code: str, message: str, category: str, detail: dict) -> Fault:
    """Construct a fault (data, never raised)."""
    return {"code": code, "message": message, "category": category, "detail": detail}


def ok(value: object) -> Result:
    """A successful result carrying a value."""
    return {"ok": value}


def err(failure: Fault) -> Result:
    """A failed result carrying a fault."""
    return {"err": failure}
