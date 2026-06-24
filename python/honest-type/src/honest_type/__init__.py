"""honest-type — the pure-function-table type system of the Honest Framework.

Unit 1 (this release): recognizers + vocabulary construction with reserved-word and
overlap validation, plus the data shapes. classify() and chains follow.
"""

from honest_type.boundary import (
    DEFAULT_REJECTION_POLICY,
    catch_at_boundary,
    check_rejections,
)
from honest_type.chains import (
    chain,
    execute_chain,
    execute_chain_async,
    is_link,
    link,
    link_meta,
    validate_all,
)
from honest_type.classify import classify
from honest_type.recognizers import insensitive, predicate, recognize
from honest_type.reserved import RESERVED_WORDS, is_reserved
from honest_type.state_machine import StateMachineError, state_machine, transition
from honest_type.types import Fault, Rejection, Ticket, err, fault, ok, rejection, ticket
from honest_type.vocabulary import (
    VocabularyError,
    auto_binding,
    binding,
    composed,
    maybe,
    merge,
    vocabulary,
)

__all__ = [
    "classify",
    "chain",
    "execute_chain",
    "execute_chain_async",
    "validate_all",
    "link",
    "is_link",
    "link_meta",
    "catch_at_boundary",
    "check_rejections",
    "DEFAULT_REJECTION_POLICY",
    "ok",
    "err",
    "vocabulary",
    "binding",
    "auto_binding",
    "composed",
    "maybe",
    "merge",
    "predicate",
    "insensitive",
    "recognize",
    "VocabularyError",
    "state_machine",
    "transition",
    "StateMachineError",
    "RESERVED_WORDS",
    "is_reserved",
    "Ticket",
    "Rejection",
    "Fault",
    "ticket",
    "rejection",
    "fault",
]
