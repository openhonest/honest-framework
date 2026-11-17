"""honest-state: the single-mutator law and the taxonomy of state kinds, as data.

A small, all-pure, boundary-less library. It ships no primitives: it states the one law that governs
every kind of state — every declared piece of state has exactly one mutator — names each of the ten
state kinds with its home store and its single mutator (§1.2), and decides the law's two questions
(a legitimate second mutator, §1.1; the DOM-region classification, §1.3).

__all__ is exactly the five public functions a sibling module or the conformance harness reaches. The
three dom-region dispatch handlers are importable by name (the laws import them) but stay out of __all__;
the dispatch table reaches them.
"""

from honest_state.dom_region import (
    classify_dom_region,
    server_state_region,
    side_effect_region,
    user_state_region,
)
from honest_state.law import names_one_mutator, second_mutator_legitimate
from honest_state.taxonomy import mutator_of, state_kinds

__all__ = [
    "state_kinds",
    "mutator_of",
    "second_mutator_legitimate",
    "names_one_mutator",
    "classify_dom_region",
]
