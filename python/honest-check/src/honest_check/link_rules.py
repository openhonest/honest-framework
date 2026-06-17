"""Chain / link rules (spec §4.2, §10): HC001, HC002, HC009.

HC001: a function used as a chain link without @link metadata.
HC002: adjacent links whose type flow does not connect (next.accepts not
covered by prev.emits).
HC009: a predicate (lambda) whose body may throw on non-matching input.

HC008 (link-tier impurity) overlaps HC-P004 (already errors on I/O in any
non-boundary function) and HC010 (emission never produced, needs manifest-
assignment analysis) are deferred.
"""
from __future__ import annotations

from honest_check.declgraph import (
    chain_link_args,
    link_definitions,
    local_function_names,
)
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, descendants, find_by_type, line_of, node_text


# --- HC001: link missing vocabulary ---------------------------------------


def check_hc001(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    links = link_definitions(root, src)
    local_fns = local_function_names(root, src)
    for call, names in chain_link_args(root, src):
        for name in names:
            if name is None:
                continue
            # A locally-defined function used as a link but not declared @link.
            if name in local_fns and name not in links:
                out.append(diagnostic(
                    "HC001", "error",
                    f"Function '{name}' is used as a chain link but has no "
                    "vocabulary declared. Wrap it with @link(accepts=..., emits=...).",
                    path, line_of(call), col_of(call)))
    return out


# --- HC002: chain type mismatch -------------------------------------------


def check_hc002(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    links = link_definitions(root, src)
    for call, names in chain_link_args(root, src):
        seq = [links.get(n) if n is not None else None for n in names]
        for i in range(1, len(seq)):
            prev, nxt = seq[i - 1], seq[i]
            if prev is None or nxt is None:
                continue
            missing = nxt["accepts"] - prev["emits"]
            if missing:
                out.append(diagnostic(
                    "HC002", "error",
                    f"Link '{names[i]}' accepts types not provided by previous "
                    f"link '{names[i - 1]}': {sorted(missing)}.",
                    path, line_of(call), col_of(call)))
    return out


# --- HC009: predicate may throw -------------------------------------------


def _risky_nodes(body, src: bytes) -> list[str]:
    risky: list[str] = []
    for node in descendants(body):
        if node.type == "call":
            func = node.child_by_field_name("function")
            if func is not None and func.type == "identifier" and node_text(func, src) in ("int", "float"):
                risky.append(node_text(func, src) + "()")
        elif node.type == "subscript":
            risky.append("index")
        elif node.type == "binary_operator":
            if any(c.type in ("/", "//") for c in node.children):
                risky.append("division")
    return risky


def check_hc009(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for lam in find_by_type(root, "lambda"):
        body = lam.child_by_field_name("body")
        if body is None:
            continue
        risky = _risky_nodes(body, src)
        if risky:
            out.append(diagnostic(
                "HC009", "warning",
                f"Predicate may throw on non-matching input ({sorted(set(risky))}). "
                "Guard with isinstance() or wrap in try/except.",
                path, line_of(lam), col_of(lam)))
    return out


LINK_CHECKS = [
    check_hc001,
    check_hc002,
    check_hc009,
]
