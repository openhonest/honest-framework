"""The Result envelope and fault constructor (spec §10.1, §11.2).

A link / chain returns exactly one of `ok(manifest)` or `err(fault)`. These
are plain dicts stamped with their key — not classes. `fault()` always
resolves a category (spec §11.2: a fault without a category is itself a
server error).
"""
from __future__ import annotations

from honest_type.types import FAULT_REGISTRY, Fault


def fault(
    code: str,
    message: str,
    category: str | None = None,
    detail=None,
    link=None,
    input=None,
    results=None,
) -> Fault:
    """Construct a fault. Category is required by the spec; if not given it is
    resolved from the framework registry, defaulting to "server" for any
    unknown code (an uncategorized fault is a server error)."""
    if category is None:
        category = FAULT_REGISTRY.get(code, "server")
    out: Fault = {"code": code, "message": message, "category": category}
    if detail is not None:
        out["detail"] = detail
    if link is not None:
        out["link"] = link
    if input is not None:
        out["input"] = input
    if results is not None:
        out["results"] = results
    return out


def ok(manifest) -> dict:
    return {"ok": manifest}


def err(f: Fault) -> dict:
    return {"err": f}


def is_ok(result) -> bool:
    return isinstance(result, dict) and "ok" in result


def is_err(result) -> bool:
    return isinstance(result, dict) and "err" in result


def is_fault(value) -> bool:
    """A bare fault (not wrapped in a Result) — has the fault triad."""
    return (
        isinstance(value, dict)
        and "code" in value
        and "category" in value
        and "message" in value
    )
