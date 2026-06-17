"""Binding tables (spec §4.3, §5.3, §6).

A binding maps a base-type or composed-type name to a slot name, or to a
maybe(slot) for optional bindings. `auto_binding` produces the identity
mapping (type name == slot name) used when classify() is called without an
explicit binding.
"""
from __future__ import annotations

from honest_type.types import Vocabulary, is_maybe, maybe, unwrap_maybe  # noqa: F401  (re-exported)


def binding(rules: dict) -> dict:
    """Pure constructor. Values are slot names or maybe(slot)."""
    return dict(rules)


def auto_binding(vocab: Vocabulary) -> dict:
    """Identity mapping: every base and composed type name becomes its own
    slot name (spec §6)."""
    result: dict = {}
    for type_name in vocab["base_types"]:
        result[type_name] = type_name
    for comp in vocab["composed_types"]:
        result[comp["name"]] = comp["name"]
    return result
