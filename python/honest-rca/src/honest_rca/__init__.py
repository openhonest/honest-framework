"""honest-rca — the apophatic root-cause solver. Trace a failure through a bounded, hashable evidence
set under a versioned method to a fixpoint, and attest the negative: under this evidence and method
the chain terminates at X, and no upstream factor was identified. Never "X is the root cause"."""

from honest_rca.types import (
    BOUND_KINDS,
    DETERMINISTIC_SIGNALS,
    EVIDENCE_KINDS,
    RELATION_SIGNAL,
    SIGNAL_KINDS,
    causal_edge,
)
from honest_rca.evidence import evidence_hash, evidence_set
from honest_rca.edges import (
    causal_graph,
    change_correlation_edges,
    controlflow_edges,
    dataflow_edges,
    temporal_edges,
)
from honest_rca.trace import terminus, trace
from honest_rca.attest import attest, bound, terminus_is_design_root, validate_attestation

__all__ = [
    "BOUND_KINDS",
    "DETERMINISTIC_SIGNALS",
    "EVIDENCE_KINDS",
    "RELATION_SIGNAL",
    "SIGNAL_KINDS",
    "attest",
    "bound",
    "causal_edge",
    "causal_graph",
    "change_correlation_edges",
    "controlflow_edges",
    "dataflow_edges",
    "evidence_hash",
    "evidence_set",
    "temporal_edges",
    "terminus",
    "terminus_is_design_root",
    "trace",
    "validate_attestation",
]
