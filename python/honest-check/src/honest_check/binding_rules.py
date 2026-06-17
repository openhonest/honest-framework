"""Vocabulary/binding static rules (spec §4.2): HC004, HC005, HC-P014.

These pair a vocabulary with its binding via classify() call sites. HC-P010
(non-serializable return) is deferred — HC-P003 already bans the classes whose
instances it would catch; it returns with richer type analysis later.
"""
from __future__ import annotations

from honest_check.declgraph import find_classify_pairings
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, line_of


def _composed_names(vocab):
    return {c["name"] for c in vocab["composed_types"]}


def _composed_used_types(vocab):
    used = set()
    for c in vocab["composed_types"]:
        used |= set(c["requires"])
        if c["captures"]:
            used.add(c["captures"])
    return used


# --- HC004: dead vocabulary type ------------------------------------------


def check_hc004(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for vocab, binding in find_classify_pairings(root, src):
        if binding is None:
            continue   # auto-binding binds every type by construction
        bound = set(binding["entries"])
        used_in_composed = _composed_used_types(vocab)
        loc = vocab["node"]
        for type_name in vocab["base_types"]:
            if type_name not in bound and type_name not in used_in_composed:
                out.append(diagnostic(
                    "HC004", "warning",
                    f"Type '{type_name}' defined in vocabulary but never bound or composed.",
                    path, line_of(loc), col_of(loc)))
    return out


# --- HC005: unused binding entry ------------------------------------------


def check_hc005(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for vocab, binding in find_classify_pairings(root, src):
        if binding is None:
            continue
        known = set(vocab["base_types"]) | _composed_names(vocab)
        loc = binding["node"]
        for type_name in binding["entries"]:
            if type_name not in known:
                out.append(diagnostic(
                    "HC005", "warning",
                    f"Binding references type '{type_name}' not found in vocabulary.",
                    path, line_of(loc), col_of(loc)))
    return out


# --- HC-P014: recognizer reused across slots ------------------------------


def _comparable_key(recognizer):
    """A key two slots can be compared on, or None if not statically comparable
    (inline predicates each get a unique node and cannot be compared)."""
    kind, payload = recognizer
    if kind in ("set", "insensitive", "ref"):
        return (kind, payload)
    return None


def check_hc_p014(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for vocab, binding in find_classify_pairings(root, src):
        if binding is None:
            continue
        base = vocab["base_types"]
        loc = binding["node"]
        by_recognizer: dict = {}
        for type_name, slot in binding["entries"].items():
            recognizer = base.get(type_name)
            if recognizer is None:
                continue
            key = _comparable_key(recognizer)
            if key is not None:
                by_recognizer.setdefault(key, []).append(slot)
        for key, slots in by_recognizer.items():
            if len(slots) > 1:
                out.append(diagnostic(
                    "HC-P014", "error",
                    f"One recognizer is bound to multiple slots {sorted(s for s in slots if s)}. "
                    "Each slot must have a semantically distinct recognizer, or the "
                    "chain contract cannot catch a swap between them.",
                    path, line_of(loc), col_of(loc)))
    return out


BINDING_CHECKS = [
    check_hc004,
    check_hc005,
    check_hc_p014,
]
