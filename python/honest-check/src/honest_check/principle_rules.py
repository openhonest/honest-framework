"""Honest-Code principle rules that are purely AST-structural (spec §4.2).

This unit (3a) covers the rules needing no declaration graph, boundary, role,
or binding analysis: HC-P002 (mutating methods), HC-P007 (instance state in
constructor), HC-P011 (framework lifecycle hooks), HC-P016 (nonlocal closure
over mutable state). Rules requiring boundary/role/link/auth context land in
later sub-units.
"""
from __future__ import annotations

from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text


def _self_attr_name(node, src: bytes) -> str | None:
    """If node is `self.<attr>`, return <attr>, else None."""
    if node is None or node.type != "attribute":
        return None
    obj = node.child_by_field_name("object")
    attr = node.child_by_field_name("attribute")
    if (obj is not None and obj.type == "identifier" and node_text(obj, src) == "self"
            and attr is not None):
        return node_text(attr, src)
    return None


def _within_fn(fn, type_name: str) -> list:
    """Nodes of a type inside a function, not descending into nested functions."""
    body = fn.child_by_field_name("body")
    out: list = []
    stack = list(body.children) if body is not None else []
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            continue
        if node.type == type_name:
            out.append(node)
        stack.extend(node.children)
    return out


def _methods(cls):
    body = cls.child_by_field_name("body")
    if body is None:
        return []
    return [c for c in body.named_children if c.type == "function_definition"]


def _self_assignments(method, src: bytes):
    """(attr_name, node) for every assignment whose target is self.<attr>."""
    out = []
    for kind in ("assignment", "augmented_assignment"):
        for assign in _within_fn(method, kind):
            attr = _self_attr_name(assign.child_by_field_name("left"), src)
            if attr is not None:
                out.append((attr, assign))
    return out


# --- HC-P002: class with mutating methods ---------------------------------


def check_hc_p002(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for cls in find_by_type(root, "class_definition"):
        for method in _methods(cls):
            name_node = method.child_by_field_name("name")
            mname = node_text(name_node, src) if name_node is not None else ""
            for _attr, assign in _self_assignments(method, src):
                severity = "warning" if mname == "__init__" else "error"
                out.append(diagnostic(
                    "HC-P002", severity,
                    f"Method '{mname}' mutates self. Use a TypedDict + pure function.",
                    path, line_of(assign), col_of(assign)))
    return out


# --- HC-P007: instance state in constructor -------------------------------


def check_hc_p007(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for cls in find_by_type(root, "class_definition"):
        for method in _methods(cls):
            name_node = method.child_by_field_name("name")
            if name_node is None or node_text(name_node, src) != "__init__":
                continue
            for attr, assign in _self_assignments(method, src):
                if attr.startswith("_"):
                    out.append(diagnostic(
                        "HC-P007", "warning",
                        f"Instance state 'self.{attr}' set in constructor. "
                        "Pass as a parameter or use a context manager.",
                        path, line_of(assign), col_of(assign)))
    return out


# --- HC-P011: framework lifecycle hooks -----------------------------------

_LIFECYCLE_HOOKS = frozenset({
    "useEffect", "useLayoutEffect", "componentDidMount", "componentDidUpdate",
    "componentWillUnmount", "ngOnInit", "ngOnDestroy",
    "addEventListener", "removeEventListener",
})


def _call_tail_name(call, src: bytes) -> str:
    func = call.child_by_field_name("function")
    if func is None:
        return ""
    if func.type == "identifier":
        return node_text(func, src)
    if func.type == "attribute":
        attr = func.child_by_field_name("attribute")
        return node_text(attr, src) if attr is not None else ""
    return ""


def check_hc_p011(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for call in find_by_type(root, "call"):
        if _call_tail_name(call, src) in _LIFECYCLE_HOOKS:
            out.append(diagnostic(
                "HC-P011", "error",
                f"Lifecycle hook '{_call_tail_name(call, src)}'. "
                "Use HTMX attributes or server-rendered HTML.",
                path, line_of(call), col_of(call)))
    return out


# --- HC-P016: nonlocal closure over mutable state -------------------------


def check_hc_p016(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for fn in find_by_type(root, "function_definition"):
        nonlocal_names: set[str] = set()
        for nl in _within_fn(fn, "nonlocal_statement"):
            for child in nl.named_children:
                if child.type == "identifier":
                    nonlocal_names.add(node_text(child, src))
        if not nonlocal_names:
            continue
        mutated: set[str] = set()
        for kind in ("assignment", "augmented_assignment"):
            for assign in _within_fn(fn, kind):
                left = assign.child_by_field_name("left")
                if left is not None and left.type == "identifier":
                    mutated.add(node_text(left, src))
        captured = nonlocal_names & mutated
        if captured:
            name_node = fn.child_by_field_name("name")
            fname = node_text(name_node, src) if name_node is not None else "<fn>"
            out.append(diagnostic(
                "HC-P016", "error",
                f"Function '{fname}' captures {sorted(captured)} via nonlocal and "
                "mutates it. Closures may not carry mutable state — use pure "
                "parameters or move state into persist.",
                path, line_of(fn), col_of(fn)))
    return out


PRINCIPLE_CHECKS = [
    check_hc_p002,
    check_hc_p007,
    check_hc_p011,
    check_hc_p016,
]
