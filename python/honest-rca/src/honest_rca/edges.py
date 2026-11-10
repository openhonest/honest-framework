"""Edge construction (spec §5): each deterministic signal's detector grounds an edge for every
recorded relation of its kind, and causal_graph applies the signals M enables. The detectors are
pure and dispatched by signal kind through a table, never an if/elif chain."""

from honest_rca.types import DETERMINISTIC_SIGNALS, causal_edge


# Dispatch by signal kind (§5): each deterministic signal grounds an edge for every recorded
# relation of its kind, so the kind maps to the evidence-item key that records its relation —
# dataflow from flows_to (parse), controlflow from controls (parse), change_correlation from
# changed_with (history), temporal from precedes (the event log). judgment builds no edges of its
# own; a judgment edge is supplied.
_SIGNAL_RELATION = {
    "dataflow": "flows_to",
    "controlflow": "controls",
    "change_correlation": "changed_with",
    "temporal": "precedes",
}


def signal_edges(items, kind):
    """A grounded edge for every recorded relation of one deterministic signal kind (§5): the cause
    reaches the effect through that signal, read from the item key the kind maps to in
    _SIGNAL_RELATION. Empty where the relation is absent. One detector parameterized by the signal
    kind rather than one copy per signal."""
    relation = _SIGNAL_RELATION[kind]
    return [causal_edge(item["id"], effect, kind) for item in items for effect in item[relation]]


def causal_graph(evidence, method, judgments):
    """Build the causal graph by applying each enabled deterministic signal's detector to the evidence,
    then adding the supplied judgment edges only when judgment is enabled in M (§5)."""
    items = evidence["items"]
    edges = []
    for signal in DETERMINISTIC_SIGNALS:
        if signal in method["signals"]:
            edges = edges + signal_edges(items, signal)
    if "judgment" in method["signals"]:
        edges = edges + list(judgments)
    return {"nodes": [item["id"] for item in items], "edges": edges}
