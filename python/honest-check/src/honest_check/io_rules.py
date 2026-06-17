"""I/O and type-check rules (spec §4.2): HC-P004, HC-P005.

HC-P004 (error): a function not declared a boundary that performs I/O or
nondeterministic operations from the §4.2 watch lists. A boundary is a function
decorated `@boundary` or `@link(boundary=True)`; legitimate boundary code that
is not so decorated declares its intent via suppression (`# honest: disable
HC-P004`). HC-P005 (warning): isinstance()/type() in non-boundary business logic.

HC008 (link-tier impurity warning) is the link-scoped form of HC-P004 and lands
with @link metadata extraction in a later sub-unit.
"""
from __future__ import annotations

from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text
from honest_check.watchlists import (
    IO_PYTHON,
    NONDETERMINISTIC_PYTHON,
    matches_watchlist,
)


def _dotted_name(node, src: bytes) -> str:
    if node is None:
        return ""
    if node.type == "identifier":
        return node_text(node, src)
    if node.type == "attribute":
        obj = _dotted_name(node.child_by_field_name("object"), src)
        attr = node.child_by_field_name("attribute")
        attr_name = node_text(attr, src) if attr is not None else ""
        return f"{obj}.{attr_name}" if obj else attr_name
    return ""


def _dotted_call_name(call, src: bytes) -> str:
    return _dotted_name(call.child_by_field_name("function"), src)


def _is_boundary_fn(fn, src: bytes) -> bool:
    parent = fn.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    for child in parent.children:
        if child.type != "decorator":
            continue
        expr = child.named_children[0] if child.named_children else None
        if expr is None:
            continue
        if expr.type == "identifier" and node_text(expr, src) == "boundary":
            return True
        if expr.type == "call":
            func = expr.child_by_field_name("function")
            tail = _dotted_name(func, src).split(".")[-1]
            if tail == "link":
                args = expr.child_by_field_name("arguments")
                for a in (args.named_children if args is not None else []):
                    if a.type == "keyword_argument":
                        name = a.child_by_field_name("name")
                        value = a.child_by_field_name("value")
                        if (name is not None and node_text(name, src) == "boundary"
                                and value is not None and value.type == "true"):
                            return True
    return False


def _direct_calls(fn):
    """Call nodes inside a function, not descending into nested functions."""
    body = fn.child_by_field_name("body")
    out = []
    stack = list(body.children) if body is not None else []
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            continue
        if node.type == "call":
            out.append(node)
        stack.extend(node.children)
    return out


def _enclosing_function(node):
    cur = node.parent
    while cur is not None:
        if cur.type == "function_definition":
            return cur
        cur = cur.parent
    return None


# --- HC-P004: I/O inside a non-boundary function --------------------------


def check_hc_p004(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for fn in find_by_type(root, "function_definition"):
        if _is_boundary_fn(fn, src):
            continue
        for call in _direct_calls(fn):
            name = _dotted_call_name(call, src)
            if not name:
                continue
            if matches_watchlist(name, IO_PYTHON):
                out.append(diagnostic(
                    "HC-P004", "error",
                    f"I/O '{name}()' in non-boundary function. Move it behind a "
                    "boundary (@boundary / @link(boundary=True)).",
                    path, line_of(call), col_of(call)))
            elif matches_watchlist(name, NONDETERMINISTIC_PYTHON):
                out.append(diagnostic(
                    "HC-P004", "error",
                    f"Nondeterministic call '{name}()' in non-boundary function. "
                    "Pass the value in, or move it behind a boundary.",
                    path, line_of(call), col_of(call)))
    return out


# --- HC-P005: isinstance()/type() in business logic -----------------------


def check_hc_p005(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for call in find_by_type(root, "call"):
        if _dotted_call_name(call, src) not in ("isinstance", "type"):
            continue
        enclosing = _enclosing_function(call)
        if enclosing is not None and _is_boundary_fn(enclosing, src):
            continue
        out.append(diagnostic(
            "HC-P005", "warning",
            "isinstance()/type() in business logic — consider a vocabulary "
            "declaration instead.",
            path, line_of(call), col_of(call)))
    return out


IO_CHECKS = [
    check_hc_p004,
    check_hc_p005,
]
