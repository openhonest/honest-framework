"""honest-type data structures and bounded vocabularies (spec §7, §10, §11).

All data is TypedDict. Recognizers are tagged data so classify() dispatches by
a table on `kind`, never an isinstance ladder. No classes, no behavior.
"""
from __future__ import annotations

from typing import Callable, NotRequired, TypedDict, Union


# --- Recognizers (tagged data) -------------------------------------------


class SetRecognizer(TypedDict):
    kind: str                  # "set"
    members: frozenset[str]


class InsensitiveRecognizer(TypedDict):
    kind: str                  # "insensitive"
    members: frozenset[str]    # lowercased; original token preserved in the ticket


class PredicateRecognizer(TypedDict):
    kind: str                  # "predicate"
    fn: Callable[[str], bool]


Recognizer = Union[SetRecognizer, InsensitiveRecognizer, PredicateRecognizer]


def set_recognizer(members) -> SetRecognizer:
    return {"kind": "set", "members": frozenset(members)}


def insensitive(members) -> InsensitiveRecognizer:
    """Case-insensitive Set recognizer (spec §9.1). Members lowercased for
    matching; the original token value is preserved in the ticket."""
    return {"kind": "insensitive", "members": frozenset(m.lower() for m in members)}


def predicate(fn: Callable[[str], bool]) -> PredicateRecognizer:
    return {"kind": "predicate", "fn": fn}


# --- Maybe (optional binding, spec §5) -----------------------------------


class Maybe(TypedDict):
    maybe: str                 # wrapped slot name (binding) or base type (capture)


def maybe(name: str) -> Maybe:
    return {"maybe": name}


def is_maybe(value: object) -> bool:
    return isinstance(value, dict) and "maybe" in value


def unwrap_maybe(value) -> str:
    """Return the slot/type name whether or not it is wrapped in maybe()."""
    return value["maybe"] if is_maybe(value) else value


# Nothing — explicit absence in the manifest (spec §5.6 Python mapping).
Nothing = None


# --- Compositional types (spec §4) ---------------------------------------


class ComposedType(TypedDict):
    name: str
    requires: dict[str, str]   # base type name -> required value
    captures: object           # base type name (str) or maybe(type) wrapper


def composed(name: str, requires: dict[str, str], captures) -> ComposedType:
    return {"name": name, "requires": dict(requires), "captures": captures}


# --- Vocabulary + binding ------------------------------------------------


class Vocabulary(TypedDict):
    base_types: dict[str, Recognizer]
    composed_types: list[ComposedType]


# Binding maps a type/composed name to a slot name, or maybe(slot):
#   Binding = dict[str, str | Maybe]


# --- classify() outputs (spec §7) ----------------------------------------


class Ticket(TypedDict):
    type: str
    value: str


def ticket(type: str, value: str) -> Ticket:
    return {"type": type, "value": value}


class Rejection(TypedDict):
    token: NotRequired[object]       # str, or None for missing_required
    reason: str                      # one of REJECTION_REASONS
    detail: NotRequired[object]      # conflicting type/slot, etc.


def rejection(token, reason: str, detail=None) -> Rejection:
    out: Rejection = {"token": token, "reason": reason}
    if detail is not None:
        out["detail"] = detail
    return out


# Manifest is a flat dict[str, str | None] plus an optional "_rejections" list;
# kept as a plain dict. "_rejections" is present only when non-empty (spec §7).


# --- Fault (spec §11) ----------------------------------------------------


class Fault(TypedDict):
    code: str
    message: str
    category: str                    # "client" | "server"
    detail: NotRequired[object]      # structured context (offending word, slot, etc.)
    link: NotRequired[object]
    input: NotRequired[object]
    results: NotRequired[list]       # only for validation_failed


# --- Bounded vocabularies ------------------------------------------------

# The seven rejection reason codes (spec §7 rejection, §9 rule summary).
REJECTION_REASONS: frozenset[str] = frozenset({
    "unrecognized",
    "reserved_word",
    "unbound_type",
    "duplicate_slot",
    "missing_required",
    "empty_token",
    "null_token",
})

CATEGORIES: frozenset[str] = frozenset({"client", "server"})

# Framework fault-code registry: code -> category (spec §11.3), plus the
# vocabulary-construction fault (§14.5) and the boundary's unhandled-exception
# fault (§11.4).
FAULT_REGISTRY: dict[str, str] = {
    "validation_failed":           "client",
    "missing_required":            "client",
    "unrecognized":                "client",
    "empty_token":                 "client",
    "null_token":                  "client",
    "duplicate_slot":              "client",
    "predicate_error":             "server",
    "non_string_token":            "server",
    "non_result_return":           "server",
    "unbound_type":                "server",
    "reserved_word":               "server",
    "reserved_word_in_vocabulary": "server",
    "unhandled_exception":         "server",
}

FAULT_CODES: frozenset[str] = frozenset(FAULT_REGISTRY)

# HTTP mapping for the web boundary (spec §11.4); generic boundaries supply
# their own output table.
FAULT_TO_HTTP: dict[str, int] = {
    "validation_failed": 422,
    "missing_required":  400,
    "unrecognized":      400,
    "empty_token":       400,
    "null_token":        400,
    "duplicate_slot":    400,
    "predicate_error":   500,
    "non_string_token":  500,
    "non_result_return": 500,
    "unbound_type":      500,
    "reserved_word":     500,
}
