"""The single-mutator law's two questions (honest-state-architecture.md §1.1, §1.2).

Both functions are pure, take bounded values, and return a bool. There is no fault: a bool and a list
are bounded inputs, so there is no miss to report.
"""


def second_mutator_legitimate(honest: bool, disjoint: bool) -> bool:
    """Decide whether a SECOND mutator of a store is legitimate under the single-mutator law (§1.1).
    It is legitimate if and only if it is BOTH honest — it does not hide the state it mutates — AND
    disjoint — it touches no state another mutator already owns. This admits honest-alerts as a
    legitimate second mutator of the DOM (non-hiding, never touching a manifest slot) and rejects any
    mutator that hides state or reaches into an owned region."""
    return honest and disjoint


def names_one_mutator(mutators: list[str]) -> bool:
    """The §1.2 acceptance test for a candidate state kind: can you name exactly one mutator? True when
    the list names exactly one, false otherwise. A false answer is the signal to split the kind, not to
    allow two mutators."""
    return len(mutators) == 1
