"""The causal IR of honest-rca (spec section 2, .hd type declarations). Every value is a plain record
— data, no behaviour; all TypedDicts (no classes) plus one dict type alias. A Symptom names what
happened and never why; an EvidenceItem carries one piece of the bounded evidence and its recorded
relations; the EvidenceSet is the hashed body; a CausalEdge is one cause->effect link; the Method is
the versioned signal set; the CausalGraph is the edges the method produced; the Bound is the stated
limit; the Attestation is the negative claim.

The vocabulary-bound fields (kind, signal) are plain str here; the closed sets that bound them live in
vocabularies.py and are enforced by honest-test, not by a runtime type.
"""

from typing import TypedDict


class Symptom(TypedDict):
    """The observed failure, stated precisely and kept separate from any guess at its cause (spec
    section 2). site is the EvidenceItem id where the failure was observed — the node trace starts
    upstream from. A Symptom names what happened, never why."""

    id: str
    description: str
    site: str


class EvidenceItem(TypedDict):
    """One piece of the bounded evidence (spec section 2). kind is one of EVIDENCE_KINDS. ref locates
    the item in the world. The four relation fields carry the recorded relations honest-rca grounds
    edges on, one per deterministic signal, each a list of downstream item ids (the effects this item
    causes). category, when non-empty, marks the item as a design root and names the bug category it
    represents; an ordinary item leaves it empty."""

    id: str
    kind: str
    ref: str
    flows_to: list[str]
    controls: list[str]
    changed_with: list[str]
    precedes: list[str]
    category: str


class EvidenceSet(TypedDict):
    """The bounded body of evidence E (spec sections 2, 3). items is the list of EvidenceItem values
    assembled at the boundary. hash is the order-independent digest evidence_hash derives — the same
    items in any order yield the same hash."""

    items: list[EvidenceItem]
    hash: str


class CausalEdge(TypedDict):
    """A directed cause->effect link in the causal graph (spec section 2). signal is one of
    SIGNAL_KINDS. marked is true exactly when signal is judgment — a reserved judgment reproducible
    only up to the judge's version; a grounded edge (marked false) is a recorded fact."""

    cause: str
    effect: str
    signal: str
    marked: bool


class Method(TypedDict):
    """The versioned causal method M (spec sections 2, 4). version makes the method reproducible.
    signals is the enabled subset of SIGNAL_KINDS — the grounds M will accept. traversal names the
    upstream-traversal rule trace follows."""

    version: str
    signals: list[str]
    traversal: str


class CausalGraph(TypedDict):
    """The causal graph over E (spec section 2). nodes is the list of item ids. edges is the list of
    CausalEdge values M produced from E's recorded relations plus the enabled judgment edges."""

    nodes: list[str]
    edges: list[CausalEdge]


# The stated limit on the search (spec sections 2, 7.1): a mapping from each of the two BOUND_KINDS
# words to its list of identifiers, so the two incompleteness modes are a closed, enumerable key space
# rather than two free-standing fields. outside_evidence carries the item ids the evidence's relations
# reference but that are absent from E; invisible_to_method carries the referenced edges no enabled
# signal grounded. A Bound is always present, even when both lists are empty.
Bound = dict[str, list[str]]


class Attestation(TypedDict):
    """The output, the negative claim (spec sections 2, 7). terminus is the node past which the bounded
    search finds nothing; chain is the ordered path from the symptom to the terminus; marked_edges are
    the judgment edges the chain relied on. bound is the computed Bound. category is copied from the
    terminus item — empty for an ordinary terminus, the named bug category for a design root; poka_yoke
    is present exactly when category is non-empty. The record has no field that asserts 'X is the
    root'; its semantics are fixed as the negative."""

    symptom: Symptom
    evidence_hash: str
    method_version: str
    terminus: str
    chain: list[str]
    marked_edges: list[CausalEdge]
    bound: Bound
    category: str
    poka_yoke: str
