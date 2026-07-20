"""The causal IR's vocabularies and the edge constructor (spec §2). Records are plain dicts —
data, no behaviour. The three closed vocabularies make honest-rca exhaustively testable."""

# The five evidence sources the methodology names (§2.1).
EVIDENCE_KINDS = ("code", "event", "history", "config", "deploy")

# The four deterministic causal grounds plus the marked, reserved-judgment edge (§2.1).
SIGNAL_KINDS = ("dataflow", "controlflow", "change_correlation", "temporal", "judgment")

# The deterministic grounds — every edge one of these produces is recorded fact, not judgment.
DETERMINISTIC_SIGNALS = ("dataflow", "controlflow", "change_correlation", "temporal")

# The two ways a bounded search can be incomplete (§2.1).
BOUND_KINDS = ("outside_evidence", "invisible_to_method")

# Which deterministic signal each recorded relation grounds. The mapping is the single source for
# both edge construction and the bound: a relation whose signal M did not enable is invisible to M.
RELATION_SIGNAL = {
    "flows_to": "dataflow",
    "controls": "controlflow",
    "changed_with": "change_correlation",
    "precedes": "temporal",
}


def causal_edge(cause, effect, signal):
    """A directed cause->effect edge (§2). marked is true exactly when the signal is judgment — the
    'pseudo' in a pseudo-proof, reproducible only up to the judge's version. Pure."""
    return {"cause": cause, "effect": effect, "signal": signal, "marked": signal == "judgment"}
