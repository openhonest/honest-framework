"""honest-type — pure function tables as the type system.

A Recognizer is a predicate String → bool. A Vocabulary is a dict mapping
type names to recognizers. A Binding maps type names to slot names. A
Ticket is a classified token. A Manifest is the fully resolved binding.

Composition works via Chain (ordered fn names) and the `pipe` helper.
Classification is one dict lookup and one function call — no hierarchies.

No classes. No methods. Functions in, data out.
"""
from honest_type.binding import binding, resolve_bindings
from honest_type.chain import chain, compose_chain, pipe, run_chain
from honest_type.classify import classify, classify_token, emit_rejection
from honest_type.extract import extract_cli_tokens, extract_http_tokens
from honest_type.manifest import emit_manifest
from honest_type.types import (
    Binding,
    Chain,
    ComposedType,
    Fault,
    Link,
    Manifest,
    Recognizer,
    Rejection,
    Ticket,
    Vocabulary,
)
from honest_type.vocabulary import merge_vocabularies, vocabulary

__all__ = [
    "Binding",
    "Chain",
    "ComposedType",
    "Fault",
    "Link",
    "Manifest",
    "Recognizer",
    "Rejection",
    "Ticket",
    "Vocabulary",
    "binding",
    "chain",
    "classify",
    "classify_token",
    "compose_chain",
    "emit_manifest",
    "emit_rejection",
    "extract_cli_tokens",
    "extract_http_tokens",
    "merge_vocabularies",
    "pipe",
    "resolve_bindings",
    "run_chain",
    "vocabulary",
]
