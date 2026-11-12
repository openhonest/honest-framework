"""honest-rca: the apophatic root-cause leaf of the Honest Framework (spec section 1).

A pure leaf: it builds a causal graph from a bounded, hashable evidence set under a versioned method,
traces upstream to a fixpoint, and attests the negative — never "X is the root", only "under this
evidence hash and this method version the chain terminates at X and no upstream factor was
identified". It touches no file, clock, network or environment, and nothing raises; faults travel as
data. It depends only on honest-type, whose Fault it references by name.
"""

from honest_rca.ir import (
    Attestation,
    Bound,
    CausalEdge,
    CausalGraph,
    EvidenceItem,
    EvidenceSet,
    Method,
    Symptom,
)
from honest_rca.rca import (
    attest,
    bound,
    by_signal,
    causal_graph,
    evidence_hash,
    evidence_set,
    relation_changed_with,
    relation_controls,
    relation_flows_to,
    relation_precedes,
    signal_edges,
    terminus,
    terminus_is_design_root,
    trace,
    validate_attestation,
)
from honest_rca.vocabularies import BOUND_KINDS, EVIDENCE_KINDS, SIGNAL_KINDS

# __all__ is exactly the ten public functions the .hd names as `entry "import honest_rca"` targets,
# mirroring how honest-errors narrowed __all__ to its import surface. The three bounded vocabularies,
# the IR TypedDicts, the by_signal dispatch table, and the four relation detectors are imported above
# so they stay importable module attributes (the conformance suite reads the vocabularies and calls
# the detectors directly), but they are supporting data and types, not the declared public surface.
__all__ = [
    "evidence_hash",
    "evidence_set",
    "signal_edges",
    "causal_graph",
    "trace",
    "terminus",
    "bound",
    "attest",
    "validate_attestation",
    "terminus_is_design_root",
]
