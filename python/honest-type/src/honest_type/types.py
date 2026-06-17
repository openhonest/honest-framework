"""honest-type IR. All TypedDicts + Callable aliases. No classes.

Keep in sync with tools/honest-design/examples/honest-type.hd.
"""
from __future__ import annotations

from typing import Callable, TypedDict


# A recognizer is a predicate over a token. This IS a type.
Recognizer = Callable[[str], bool]


class Vocabulary(TypedDict):
    """Named collection of recognizers. Keys are type names (e.g. "email",
    "order_id"); values are predicates that classify a string.
    """
    recognizers: dict[str, Recognizer]


class Binding(TypedDict):
    """Maps type names to slot names. Used after classification to place
    classified values in named slots: "email" → "user_email".
    """
    rules: dict[str, str]


class Ticket(TypedDict):
    """A classified token. One recognizer matched; we know the type."""
    type: str
    value: str
    slot: str  # "" if no binding was applied yet


class Manifest(TypedDict):
    """Fully resolved binding result. slot → value."""
    slots: dict[str, str]
    tickets: list[Ticket]


class Rejection(TypedDict):
    """Unrecognized token. Data, not an exception."""
    value: str
    reason: str       # e.g. "unrecognized_shape"
    attempted: list[str]  # type names that were tried and failed


class Fault(TypedDict):
    """Error in a chain. Data, not an exception. Exceptions only at the HTTP
    boundary.
    """
    code: str
    category: str   # "client" | "server"
    message: str


class ComposedType(TypedDict):
    """A vocabulary composed from multiple vocabularies. Shape unchanged
    from Vocabulary; this TypedDict documents intent.
    """
    recognizers: dict[str, Recognizer]
    sources: list[str]  # names of contributing vocabularies


class Link(TypedDict):
    """A function with its declared vocabulary and role. Unit of chain
    composition.
    """
    name: str
    role: str           # boundary_in | orchestrator | pure | boundary_out
    vocabulary: Vocabulary
    fn: Callable
    input_types: list[str]
    output_types: list[str]


class Chain(TypedDict):
    """Pipeline of links. Each link's output feeds the next link's input."""
    name: str
    links: list[Link]


# --- Bounded vocabularies (for test / check) -------------------------------

FAULT_CATEGORY_CLIENT = "client"
FAULT_CATEGORY_SERVER = "server"

REJECTION_REASONS: frozenset[str] = frozenset({
    "unrecognized_shape",
    "identity_unknown",
    "conflict",
    "auth_failed",
})
