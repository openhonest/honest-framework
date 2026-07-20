"""Edge construction (spec §5): each deterministic signal's detector grounds an edge for every
recorded relation of its kind, and causal_graph applies the signals M enables. The detectors are
pure and dispatched by signal kind through a table, never an if/elif chain."""

from honest_rca.types import DETERMINISTIC_SIGNALS, causal_edge


def dataflow_edges(items):
    """A grounded dataflow edge for each recorded flows_to relation: the cause's value reaches the
    effect (read from parse). None where the relation is absent."""
    return [causal_edge(item["id"], effect, "dataflow") for item in items for effect in item["flows_to"]]


def controlflow_edges(items):
    """A grounded controlflow edge for each recorded controls relation: the cause's branch determines
    whether the effect executes (read from parse)."""
    return [causal_edge(item["id"], effect, "controlflow") for item in items for effect in item["controls"]]


def change_correlation_edges(items):
    """A grounded change_correlation edge for each recorded changed_with relation: the cause changed
    together with the effect (read from history)."""
    return [causal_edge(item["id"], effect, "change_correlation") for item in items for effect in item["changed_with"]]


def temporal_edges(items):
    """A grounded temporal edge for each recorded precedes relation: strict happens-before in the
    event log (read from observe)."""
    return [causal_edge(item["id"], effect, "temporal") for item in items for effect in item["precedes"]]


# Dispatch by signal kind (§5). judgment builds no edges of its own — a judgment edge is supplied.
_DETECTORS = {
    "dataflow": dataflow_edges,
    "controlflow": controlflow_edges,
    "change_correlation": change_correlation_edges,
    "temporal": temporal_edges,
}


def causal_graph(evidence, method, judgments):
    """Build the causal graph by applying each enabled deterministic signal's detector to the evidence,
    then adding the supplied judgment edges only when judgment is enabled in M (§5)."""
    items = evidence["items"]
    edges = []
    for signal in DETERMINISTIC_SIGNALS:
        if signal in method["signals"]:
            edges = edges + _DETECTORS[signal](items)
    if "judgment" in method["signals"]:
        edges = edges + list(judgments)
    return {"nodes": [item["id"] for item in items], "edges": edges}
