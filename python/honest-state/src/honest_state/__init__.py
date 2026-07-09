"""honest-state: the single-mutator law and the taxonomy of state kinds (section 1).

honest-state defines no primitives. It states the law — every declared piece of state has exactly one
mutator — and names each kind's store and mutator, as data. The mechanics live in the home modules:
user state is DATAOS in honest-DOM, domain-state transitions are a honest-type state machine, server
state is honest-alerts. The law is enforced by honest-check (HC-P004, HC-P016, the boundary-write and
DOM-single-store rules, HC-SM01-05). Everything honest-state itself ships is pure.
"""

from honest_state.law import second_mutator_legitimate
from honest_state.taxonomy import dom_region_kind, mutator_of, state_kinds

__all__ = [
    "state_kinds",
    "mutator_of",
    "second_mutator_legitimate",
    "dom_region_kind",
]
