"""honest-type — the pure-function-table type system of the Honest Framework.

Unit 1 (this release): recognizers + vocabulary construction with reserved-word and
overlap validation, plus the data shapes. classify() and chains follow.
"""

from honest_type.classify import classify
from honest_type.recognizers import insensitive, predicate, recognize
from honest_type.reserved import RESERVED_WORDS, is_reserved
from honest_type.types import Fault, Rejection, Ticket, fault, rejection, ticket
from honest_type.vocabulary import VocabularyError, auto_binding, binding, vocabulary

__all__ = [
    "classify",
    "vocabulary",
    "binding",
    "auto_binding",
    "predicate",
    "insensitive",
    "recognize",
    "VocabularyError",
    "RESERVED_WORDS",
    "is_reserved",
    "Ticket",
    "Rejection",
    "Fault",
    "ticket",
    "rejection",
    "fault",
]
