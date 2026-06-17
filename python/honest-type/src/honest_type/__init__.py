"""honest-type — pure function tables as the type system.

Tokens in, manifest out. General purpose: no web, no HTTP, no I/O in the core
(the CLI is the only I/O-bearing module). See honest-type-architecture.md.
"""
from honest_type.binding import auto_binding, binding
from honest_type.boundary import (
    DEFAULT_REJECTION_POLICY,
    apply_rejection_policy,
    catch_at_boundary,
)
from honest_type.chain import (
    chain,
    execute_chain,
    execute_chain_async,
    link,
    validate_all,
)
from honest_type.classify import classify, classify_token, resolve_bindings
from honest_type.extract import extract_cli_tokens, extract_http_tokens
from honest_type.reserved import (
    RESERVED_WORDS,
    is_reserved,
    reservation_layer,
)
from honest_type.result import err, fault, is_err, is_fault, is_ok, ok
from honest_type.types import (
    CATEGORIES,
    FAULT_CODES,
    FAULT_REGISTRY,
    FAULT_TO_HTTP,
    REJECTION_REASONS,
    ComposedType,
    Fault,
    InsensitiveRecognizer,
    Maybe,
    Nothing,
    PredicateRecognizer,
    Recognizer,
    Rejection,
    SetRecognizer,
    Ticket,
    Vocabulary,
    composed,
    insensitive,
    is_maybe,
    maybe,
    predicate,
    rejection,
    set_recognizer,
    ticket,
    unwrap_maybe,
)
from honest_type.vocabulary import merge_vocabularies, vocabulary

__all__ = [
    # types + constructors
    "Recognizer", "SetRecognizer", "InsensitiveRecognizer", "PredicateRecognizer",
    "set_recognizer", "insensitive", "predicate",
    "Maybe", "maybe", "is_maybe", "unwrap_maybe", "Nothing",
    "ComposedType", "composed", "Vocabulary",
    "Ticket", "ticket", "Rejection", "rejection", "Fault",
    "REJECTION_REASONS", "CATEGORIES", "FAULT_REGISTRY", "FAULT_CODES", "FAULT_TO_HTTP",
    # reserved words
    "RESERVED_WORDS", "reservation_layer", "is_reserved",
    # result envelope
    "ok", "err", "fault", "is_ok", "is_err", "is_fault",
    # vocabulary + binding
    "vocabulary", "merge_vocabularies", "binding", "auto_binding",
    # classify
    "classify", "classify_token", "resolve_bindings",
    # chain
    "chain", "execute_chain", "execute_chain_async", "validate_all", "link",
    # boundary
    "catch_at_boundary", "apply_rejection_policy", "DEFAULT_REJECTION_POLICY",
    # extraction helpers
    "extract_http_tokens", "extract_cli_tokens",
]
