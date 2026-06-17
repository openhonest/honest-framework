"""AST-based rule checks. Each check returns a list[Diagnostic]."""
from __future__ import annotations

import ast

from honest_check.diagnostics import Diagnostic, aggregate_diagnostics


# --- HC-P003: class declarations ------------------------------------------

# Allowed base classes (TypedDict, Protocol, Exception subclasses).
_ALLOWED_BASES = {"TypedDict", "Protocol", "Generic"}
_ALLOWED_SUFFIXES = ("Error", "Exception", "Warning")


def check_hc_p003_class_declaration(tree: ast.AST, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if _class_is_allowed(node):
            continue
        out.append(Diagnostic(
            rule_id="HC-P003",
            severity="error",
            message=f"class {node.name!r} is not allowed. Use TypedDict, Protocol, or an Exception subclass.",
            source_location=f"{path}:{node.lineno}",
        ))
    return out


def _class_is_allowed(node: ast.ClassDef) -> bool:
    # Exception-suffixed name is allowed (convention for Exception subclasses).
    if any(node.name.endswith(suf) for suf in _ALLOWED_SUFFIXES):
        return True
    for base in node.bases:
        name = _base_name(base)
        if name in _ALLOWED_BASES:
            return True
        if name == "Exception" or name.endswith("Error") or name.endswith("Exception"):
            return True
    return False


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return ""


# --- HC-P001: if/elif dispatching on a discriminant ------------------------


def check_hc_p001_if_elif_else_dispatch(tree: ast.AST, path: str) -> list[Diagnostic]:
    """Heuristic: any `if X == LITERAL: ... elif X == LITERAL: ... else:`
    where X is the same variable and there are ≥2 elif branches.
    """
    out: list[Diagnostic] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        target_name = _elif_dispatch_target(node)
        chain_len = _count_elif_chain(node)
        if target_name and chain_len >= 2:
            out.append(Diagnostic(
                rule_id="HC-P001",
                severity="error",
                message=f"if/elif chain of length {chain_len + 1} dispatching on {target_name!r}. Use a dict-lookup table instead.",
                source_location=f"{path}:{node.lineno}",
            ))
    return out


def _elif_dispatch_target(node: ast.If) -> str:
    """Return the common discriminant name if the if/elif chain dispatches
    on one, else "".
    """
    name = _eq_comparison_target(node.test)
    if not name:
        return ""
    current = node
    while current.orelse and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
        next_if = current.orelse[0]
        if _eq_comparison_target(next_if.test) != name:
            return ""
        current = next_if
    return name


def _eq_comparison_target(node: ast.expr) -> str:
    if not isinstance(node, ast.Compare):
        return ""
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return ""
    left = node.left
    right = node.comparators[0]
    if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
        return left.id
    if isinstance(right, ast.Name) and isinstance(left, ast.Constant):
        return right.id
    return ""


def _count_elif_chain(node: ast.If) -> int:
    """Count how many elif branches follow (excluding the initial if)."""
    count = 0
    current = node
    while current.orelse and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
        count += 1
        current = current.orelse[0]
    return count


# --- HC-P014: catch-all / wildcard recognizers ----------------------------


def check_hc_p014_catchall(tree: ast.AST, path: str) -> list[Diagnostic]:
    """Flag lambdas / functions that return True unconditionally (likely
    catch-all recognizers).
    """
    out: list[Diagnostic] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            if _always_returns_true(node.body):
                out.append(Diagnostic(
                    rule_id="HC-P014",
                    severity="error",
                    message="lambda recognizer always returns True (catch-all). Every vocabulary must be exhaustively enumerated.",
                    source_location=f"{path}:{node.lineno}",
                ))
        elif isinstance(node, ast.FunctionDef):
            # Single-statement function that returns True directly.
            if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                ret = node.body[0].value
                if isinstance(ret, ast.Constant) and ret.value is True:
                    out.append(Diagnostic(
                        rule_id="HC-P014",
                        severity="error",
                        message=f"function {node.name!r} always returns True. If this is a recognizer, it is a banned catch-all.",
                        source_location=f"{path}:{node.lineno}",
                    ))
    return out


def _always_returns_true(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value is True


# --- Top-level driver ------------------------------------------------------


_ALL_CHECKS = [
    check_hc_p003_class_declaration,
    check_hc_p001_if_elif_else_dispatch,
    check_hc_p014_catchall,
]


def check_source(source: str, path: str = "<source>"):
    """Parse + run every check. Returns a CheckReport."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return aggregate_diagnostics([Diagnostic(
            rule_id="HC-SYN",
            severity="error",
            message=f"syntax error: {exc.msg}",
            source_location=f"{path}:{exc.lineno or 0}",
        )])

    diagnostics: list[Diagnostic] = []
    for check in _ALL_CHECKS:
        diagnostics.extend(check(tree, path))
    return aggregate_diagnostics(diagnostics)
