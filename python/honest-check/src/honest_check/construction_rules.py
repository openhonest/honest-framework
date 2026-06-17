"""Construction-time rules (spec §4.1): HC003, HC006, HC007, HC011.

These read the declaration graph (honest-framework constructor call sites)
rather than raw ASTs. HC-SM01/02/05 (state-machine vocabulary) land in the
following unit with state_machine() extraction.

Note on HC011 vs HC-P014: catch-all recognizer detection is HC011 (spec §8);
HC-P014 is "recognizer reused across slots" (a Full-tier binding rule, later).
The earlier code labeled catch-all as HC-P014 — corrected here.
"""
from __future__ import annotations

from itertools import combinations

from honest_check.declgraph import (
    extract_chain,
    extract_vocabulary,
    find_constructor_calls,
)
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text


def _vocabularies(root, src: bytes):
    return [extract_vocabulary(call, src)
            for ctor, call in find_constructor_calls(root, src) if ctor == "vocabulary"]


def _chains(root, src: bytes):
    return [extract_chain(call, src)
            for ctor, call in find_constructor_calls(root, src) if ctor == "chain"]


# --- HC003: recognizer overlap within a vocabulary ------------------------


def _set_like(repr_):
    """Lowercased members if a set/insensitive recognizer, else None."""
    kind, payload = repr_
    if kind == "set":
        return payload
    if kind == "insensitive":
        return frozenset(m.lower() for m in payload)
    return None


def check_hc003(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for vocab in _vocabularies(root, src):
        base = vocab["base_types"]
        loc = vocab["node"]
        for a, b in combinations(sorted(base), 2):
            ma, mb = _set_like(base[a]), _set_like(base[b])
            if ma is not None and mb is not None:
                shared = ma & mb
                if shared:
                    out.append(diagnostic(
                        "HC003", "error",
                        f"Types '{a}' and '{b}' share values: {sorted(shared)}",
                        path, line_of(loc), col_of(loc)))
            elif (ma is None) != (mb is None):
                out.append(diagnostic(
                    "HC003", "info",
                    f"Set x predicate overlap between '{a}' and '{b}' cannot be "
                    "checked statically — verified by honest-test.",
                    path, line_of(loc), col_of(loc)))
            else:
                out.append(diagnostic(
                    "HC003", "info",
                    f"Predicate x predicate overlap between '{a}' and '{b}' cannot "
                    "be checked statically — verified by honest-test.",
                    path, line_of(loc), col_of(loc)))
    return out


# --- HC006: composed type references unknown base type --------------------


def check_hc006(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for vocab in _vocabularies(root, src):
        base = vocab["base_types"]
        for comp in vocab["composed_types"]:
            loc = comp["node"]
            name = comp["name"] or "<composed>"
            for req_type in comp["requires"]:
                if req_type not in base:
                    out.append(diagnostic(
                        "HC006", "error",
                        f"Composed type '{name}' requires unknown base type "
                        f"'{req_type}'.",
                        path, line_of(loc), col_of(loc)))
            capture = comp["captures"]
            if capture is not None and capture not in base:
                out.append(diagnostic(
                    "HC006", "error",
                    f"Composed type '{name}' captures unknown base type "
                    f"'{capture}'.",
                    path, line_of(loc), col_of(loc)))
    return out


# --- HC007: empty chain ---------------------------------------------------


def check_hc007(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for chain in _chains(root, src):
        if chain["link_count"] == 0:
            loc = chain["node"]
            out.append(diagnostic(
                "HC007", "error", "Chain has no links.",
                path, line_of(loc), col_of(loc)))
    return out


# --- HC011: catch-all recognizer ------------------------------------------


def _block_returns_only_true(block) -> bool:
    stmts = list(block.named_children) if block is not None else []
    if len(stmts) != 1 or stmts[0].type != "return_statement":
        return False
    returned = stmts[0].named_children
    return len(returned) == 1 and returned[0].type == "true"


def check_hc011(root, src: bytes, path: str) -> list[Diagnostic]:
    """A recognizer that accepts (nearly) all inputs is not a discriminating
    type. The obvious always-true case is static; probabilistic catch-all
    detection via sampling is deferred to honest-test (spec §4.3)."""
    out: list[Diagnostic] = []
    for lam in find_by_type(root, "lambda"):
        body = lam.child_by_field_name("body")
        if body is not None and body.type == "true":
            out.append(diagnostic(
                "HC011", "error",
                "Recognizer accepts all inputs (lambda returns True) — "
                "not a discriminating type.",
                path, line_of(lam), col_of(lam)))
    for fn in find_by_type(root, "function_definition"):
        if _block_returns_only_true(fn.child_by_field_name("body")):
            name_node = fn.child_by_field_name("name")
            name = node_text(name_node, src) if name_node is not None else "<fn>"
            out.append(diagnostic(
                "HC011", "error",
                f"Recognizer '{name}' returns True for all inputs — "
                "not a discriminating type.",
                path, line_of(fn), col_of(fn)))
    return out


CONSTRUCTION_CHECKS = [
    check_hc003,
    check_hc006,
    check_hc007,
    check_hc011,
]
