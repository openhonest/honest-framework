"""Rule checks over tree-sitter nodes (spec §4).

Each rule is a pure function (root_node, source_bytes, path) -> list[Diagnostic].
Operating on tree-sitter nodes (not a language-locked AST) is what lets the
same rule logic port to JavaScript, Ruby, and Go.

This unit covers the principle rules that were already implemented, re-founded
on tree-sitter: HC-P003 (class declaration), HC-P001 (if/elif dispatch chain),
HC-P014 (catch-all recognizer), plus HC-SYN (syntax error). Construction-time
and the remaining static rules are added in subsequent units.
"""
from __future__ import annotations

from collections import Counter

from honest_check.diagnostics import Diagnostic, aggregate_diagnostics, diagnostic
from honest_check.parse import (
    col_of,
    find_by_type,
    has_syntax_error,
    line_of,
    node_text,
    parse,
    source_bytes,
)

# Spec §4.1 / §5.3: the only approved bases for a class definition.
_ALLOWED_BASES = frozenset({
    "TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error",
})


# --- HC-P003: class declaration -------------------------------------------


def _base_tail(node, src: bytes) -> str:
    """The tail identifier of a base expression: `a.b.C` -> "C", `G[T]` -> "G"."""
    if node.type == "identifier":
        return node_text(node, src)
    if node.type == "attribute":
        attr = node.child_by_field_name("attribute")
        return node_text(attr, src) if attr is not None else node_text(node, src)
    if node.type == "subscript":
        value = node.child_by_field_name("value")
        return _base_tail(value, src) if value is not None else node_text(node, src)
    return node_text(node, src)


def check_hc_p003(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for cls in find_by_type(root, "class_definition"):
        name_node = cls.child_by_field_name("name")
        name = node_text(name_node, src) if name_node is not None else "<class>"
        supers = cls.child_by_field_name("superclasses")
        if supers is None:
            out.append(diagnostic(
                "HC-P003", "error",
                f"Class '{name}' has no declared base. Honest Code permits class "
                "definitions only as subclasses of TypedDict, Protocol, ABC, or a "
                "declared Exception. Use a TypedDict or a pure function.",
                path, line_of(cls), col_of(cls)))
            continue
        for base in supers.named_children:
            if base.type == "keyword_argument":
                continue   # metaclass=... etc., not inheritance
            tail = _base_tail(base, src)
            if tail not in _ALLOWED_BASES:
                out.append(diagnostic(
                    "HC-P003", "error",
                    f"Class '{name}' inherits from '{tail}'. "
                    "Use composition over inheritance.",
                    path, line_of(cls), col_of(cls)))
    return out


# --- HC-P001: if/elif/else dispatch chain ---------------------------------


def _equality_var(cond, src: bytes) -> str | None:
    """If cond is `<identifier> == <literal>`, return the identifier name."""
    if cond is None or cond.type != "comparison_operator":
        return None
    if not any(c.type == "==" for c in cond.children):
        return None
    left = cond.child(0)
    if left is None or left.type != "identifier":
        return None
    return node_text(left, src)


def check_hc_p001(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for if_node in find_by_type(root, "if_statement"):
        conditions = [if_node.child_by_field_name("condition")]
        for child in if_node.children:
            if child.type == "elif_clause":
                conditions.append(child.child_by_field_name("condition"))
        variables = [v for v in (_equality_var(c, src) for c in conditions) if v]
        if not variables:
            continue
        top_var, count = Counter(variables).most_common(1)[0]
        if count >= 3:
            out.append(diagnostic(
                "HC-P001", "error",
                f"if/elif/else chain dispatches on '{top_var}' across {count} "
                "branches — use a dict lookup. See honest-code-principles.md §3.",
                path, line_of(if_node), col_of(if_node)))
    return out


# --- HC-P014: catch-all recognizer ----------------------------------------


def _returns_only_true(block, src: bytes) -> bool:
    stmts = [c for c in block.named_children] if block is not None else []
    if len(stmts) != 1 or stmts[0].type != "return_statement":
        return False
    returned = stmts[0].named_children
    return len(returned) == 1 and returned[0].type == "true"


def check_hc_p014(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for lam in find_by_type(root, "lambda"):
        body = lam.child_by_field_name("body")
        if body is not None and body.type == "true":
            out.append(diagnostic(
                "HC-P014", "error",
                "Recognizer accepts all inputs (lambda returns True) — "
                "not a discriminating type.",
                path, line_of(lam), col_of(lam)))
    for fn in find_by_type(root, "function_definition"):
        if _returns_only_true(fn.child_by_field_name("body"), src):
            name_node = fn.child_by_field_name("name")
            name = node_text(name_node, src) if name_node is not None else "<fn>"
            out.append(diagnostic(
                "HC-P014", "error",
                f"Recognizer '{name}' returns True for all inputs — "
                "not a discriminating type.",
                path, line_of(fn), col_of(fn)))
    return out


# --- Registry + entry point -----------------------------------------------

_ALL_CHECKS = [
    check_hc_p003,
    check_hc_p001,
    check_hc_p014,
]


def check_source(source: str, path: str = "<source>"):
    """Parse and check one source string. Returns an aggregated CheckReport."""
    src = source_bytes(source)
    tree = parse(source)
    if has_syntax_error(tree):
        errors = find_by_type(tree.root_node, "ERROR")
        line = line_of(errors[0]) if errors else 1
        return aggregate_diagnostics([diagnostic(
            "HC-SYN", "error", "source has a syntax error", path, line)])
    diagnostics: list[Diagnostic] = []
    for check in _ALL_CHECKS:
        diagnostics.extend(check(tree.root_node, src, path))
    return aggregate_diagnostics(diagnostics)
