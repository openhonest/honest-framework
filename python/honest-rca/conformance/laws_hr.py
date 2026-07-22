"""honest-rca conformance: the generative proof (the behavioural circle).

Probes every branch of the solver. The apophatic discipline is the invariant: the output is the
bounded-completeness statement — terminus, chain, marked edges, and a stated bound — never a positive
"X is the root", and validate_attestation refuses any attestation missing an element of the negative
claim, so fake RCA is unrepresentable. Each probe returns a list of failures; run() aggregates.
"""

import honest_rca
from honest_rca import (
    BOUND_KINDS,
    DETERMINISTIC_SIGNALS,
    EVIDENCE_KINDS,
    RELATION_SIGNAL,
    SIGNAL_KINDS,
    attest,
    bound,
    causal_edge,
    causal_graph,
    change_correlation_edges,
    controlflow_edges,
    dataflow_edges,
    evidence_hash,
    evidence_set,
    temporal_edges,
    terminus,
    terminus_is_design_root,
    trace,
    validate_attestation,
)


def _item(id, kind="code", ref="", flows_to=(), controls=(), changed_with=(), precedes=(), category=""):
    return {
        "id": id,
        "kind": kind,
        "ref": ref,
        "flows_to": list(flows_to),
        "controls": list(controls),
        "changed_with": list(changed_with),
        "precedes": list(precedes),
        "category": category,
    }


def _method(signals, version="m1", traversal="upstream-fixpoint"):
    return {"version": version, "signals": list(signals), "traversal": traversal}


def _symptom(site):
    return {"id": "s", "description": "boom", "site": site}


def _probe_evidence():
    bad = []
    a, b = _item("a", flows_to=["b"]), _item("b")
    if evidence_hash([a, b]) != evidence_hash([b, a]):
        bad.append("evidence_hash must be order-independent")
    if evidence_hash([a, b]) == evidence_hash([_item("a", flows_to=["c"]), b]):
        bad.append("evidence_hash must be change-sensitive")
    e = evidence_set([a, b])
    if e["items"] != [a, b] or e["hash"] != evidence_hash([a, b]):
        bad.append(f"evidence_set must carry items and the hash: {e}")
    if evidence_hash([{"id": "a", "kind": "code"}]) != evidence_hash([{"kind": "code", "id": "a"}]):
        bad.append("evidence_hash must be independent of dict key order")
    return bad


def _probe_edges():
    bad = []
    if causal_edge("a", "b", "dataflow") != {"cause": "a", "effect": "b", "signal": "dataflow", "marked": False}:
        bad.append("causal_edge grounded shape wrong")
    if causal_edge("a", "b", "judgment")["marked"] is not True:
        bad.append("causal_edge must mark a judgment edge")
    if dataflow_edges([_item("a", flows_to=["b", "c"])]) != [
        {"cause": "a", "effect": "b", "signal": "dataflow", "marked": False},
        {"cause": "a", "effect": "c", "signal": "dataflow", "marked": False},
    ]:
        bad.append("dataflow_edges must ground one edge per flows_to")
    if dataflow_edges([_item("a")]) != []:
        bad.append("dataflow_edges must be empty without the relation")
    if controlflow_edges([_item("a", controls=["b"])]) != [{"cause": "a", "effect": "b", "signal": "controlflow", "marked": False}]:
        bad.append("controlflow_edges must ground one edge per controls")
    if change_correlation_edges([_item("a", changed_with=["b"])]) != [{"cause": "a", "effect": "b", "signal": "change_correlation", "marked": False}]:
        bad.append("change_correlation_edges must ground one edge per changed_with")
    if temporal_edges([_item("a", precedes=["b"])]) != [{"cause": "a", "effect": "b", "signal": "temporal", "marked": False}]:
        bad.append("temporal_edges must ground one edge per precedes")
    # Every detector is exercised with and without its recorded relation (§10), not just dataflow: a
    # detector that grounded an edge from an absent relation would invent causation.
    for name, detector in (("controlflow", controlflow_edges), ("change_correlation", change_correlation_edges), ("temporal", temporal_edges)):
        if detector([_item("a")]) != []:
            bad.append(f"{name}_edges must be empty without its recorded relation")
    return bad


def _probe_evidence_kinds():
    """Every evidence kind can stand at a terminus (§10). The solver treats kind as data — nothing in the
    traversal may quietly privilege code over an event, a config entry, or a deploy."""
    bad = []
    for kind in EVIDENCE_KINDS:
        evidence = evidence_set([_item("root", kind=kind, flows_to=["a"]), _item("a")])
        graph = causal_graph(evidence, _method(["dataflow"]), [])
        chain = trace(graph, _symptom("a"))
        att = attest(_symptom("a"), evidence, _method(["dataflow"]), graph, chain, "")
        if att["terminus"] != "root":
            bad.append(f"an evidence item of kind {kind} must be able to stand at a terminus: {att['terminus']}")
        if validate_attestation(att) != []:
            bad.append(f"an attestation terminating at a {kind} item must be well-formed")
    return bad


def _probe_reproducibility():
    """The bounded-completeness invariant (§12): a fixed evidence set and method reproduce an identical
    attestation. This is what makes the claim verifiable by re-run rather than taken on trust — if the
    same E and M could yield two different attestations, the attestation would attest nothing."""
    bad = []
    items = [_item("c", flows_to=["b"]), _item("b", flows_to=["a"], changed_with=["a"]), _item("a")]
    method = _method(["dataflow", "change_correlation"])

    def analyse():
        evidence = evidence_set(items)
        graph = causal_graph(evidence, method, [])
        return attest(_symptom("a"), evidence, method, graph, trace(graph, _symptom("a")), "")

    first, second = analyse(), analyse()
    if first != second:
        bad.append(f"a fixed E and M must reproduce an identical attestation: {first} vs {second}")
    # Re-derived from the same items in a different order, the evidence hash — and so the attestation's
    # reproducibility key — is unchanged.
    if evidence_set(list(reversed(items)))["hash"] != evidence_set(items)["hash"]:
        bad.append("the evidence hash must not depend on the order the items were assembled in")
    return bad


def _probe_no_positive_claim():
    """The apophatic discipline made structural (§1.2, §12): the attestation record carries exactly the
    fields of a bounded-completeness statement and no field that asserts X *is* the root. There is no
    positive-claim shape to fill in, so the unfalsifiable claim cannot be expressed."""
    bad = []
    evidence = evidence_set([_item("b", flows_to=["a"]), _item("a")])
    graph = causal_graph(evidence, _method(["dataflow"]), [])
    att = attest(_symptom("a"), evidence, _method(["dataflow"]), graph, trace(graph, _symptom("a")), "")
    expected = ["bound", "category", "chain", "evidence_hash", "marked_edges", "method_version", "poka_yoke", "symptom", "terminus"]
    if sorted(att) != expected:
        bad.append(f"the attestation carries exactly the bounded-completeness fields: {sorted(att)}")
    if any(word in field for field in att for word in ("root", "cause", "because")):
        bad.append(f"no field may assert a positive cause: {sorted(att)}")
    # The bound is always present, so the claim always wears its limit on its face.
    if sorted(att["bound"]) != ["invisible_to_method", "outside_evidence"]:
        bad.append(f"the bound states both ways the search can be incomplete: {sorted(att['bound'])}")
    return bad


def _probe_graph():
    bad = []
    e = evidence_set([_item("a", flows_to=["b"], precedes=["b"]), _item("b")])
    graph = causal_graph(e, _method(["dataflow"]), [])
    if graph["nodes"] != ["a", "b"]:
        bad.append(f"causal_graph nodes wrong: {graph}")
    if graph["edges"] != [{"cause": "a", "effect": "b", "signal": "dataflow", "marked": False}]:
        bad.append(f"causal_graph must apply only enabled signals: {graph['edges']}")
    j = causal_edge("a", "b", "judgment")
    if causal_graph(evidence_set([_item("a"), _item("b")]), _method(["dataflow"]), [j])["edges"] != []:
        bad.append("causal_graph must not add judgments when judgment is disabled")
    if causal_graph(evidence_set([_item("a"), _item("b")]), _method(["dataflow", "judgment"]), [j])["edges"] != [j]:
        bad.append("causal_graph must add judgments when judgment is enabled")
    full = evidence_set([_item("a", flows_to=["b"], controls=["c"], changed_with=["d"], precedes=["e"]), _item("b"), _item("c"), _item("d"), _item("e")])
    edges = causal_graph(full, _method(["dataflow", "controlflow", "change_correlation", "temporal"]), [])["edges"]
    if edges != [
        {"cause": "a", "effect": "b", "signal": "dataflow", "marked": False},
        {"cause": "a", "effect": "c", "signal": "controlflow", "marked": False},
        {"cause": "a", "effect": "d", "signal": "change_correlation", "marked": False},
        {"cause": "a", "effect": "e", "signal": "temporal", "marked": False},
    ]:
        bad.append(f"causal_graph must dispatch each enabled signal to its own detector: {edges}")
    return bad


def _probe_trace():
    bad = []
    e = evidence_set([_item("c", flows_to=["b"]), _item("b", flows_to=["a"]), _item("a")])
    graph = causal_graph(e, _method(["dataflow"]), [])
    if trace(graph, _symptom("a")) != ["a", "b", "c"]:
        bad.append("trace must follow upstream to a fixpoint")
    if trace(causal_graph(evidence_set([_item("a")]), _method(["dataflow"]), []), _symptom("a")) != ["a"]:
        bad.append("trace must return the site alone when nothing is upstream")
    cyclic = causal_graph(evidence_set([_item("a", flows_to=["b"]), _item("b", flows_to=["a"])]), _method(["dataflow"]), [])
    if trace(cyclic, _symptom("a")) != ["a", "b"]:
        bad.append("trace must terminate on a cycle")
    if terminus(["a", "b", "c"]) != "c" or terminus([]) != "":
        bad.append("terminus must be the last node, or empty for an empty chain")
    multi = causal_graph(evidence_set([_item("b", flows_to=["a"]), _item("c", flows_to=["a"]), _item("a")]), _method(["dataflow"]), [])
    if trace(multi, _symptom("a")) != ["a", "b"]:
        bad.append("trace must take the sorted-first of several upstream causes")
    upstream_cycle = {
        "nodes": ["a", "b", "c"],
        "edges": [
            {"cause": "b", "effect": "a", "signal": "dataflow", "marked": False},
            {"cause": "c", "effect": "b", "signal": "dataflow", "marked": False},
            {"cause": "b", "effect": "c", "signal": "dataflow", "marked": False},
        ],
    }
    if trace(upstream_cycle, _symptom("a")) != ["a", "b", "c"]:
        bad.append("trace must terminate on an upstream cycle not through the start node")
    return bad


def _probe_bound():
    bad = []
    e = evidence_set([_item("a", flows_to=["b", "gone"]), _item("b")])
    graph = causal_graph(e, _method(["dataflow"]), [])
    if bound(e, graph)["outside_evidence"] != ["gone"]:
        bad.append("bound must list referenced-but-absent items")
    e2 = evidence_set([_item("a", flows_to=["b"], precedes=["b"]), _item("b")])
    if bound(e2, causal_graph(e2, _method(["dataflow"]), []))["invisible_to_method"] != [{"cause": "a", "effect": "b"}]:
        bad.append("bound must list relations no enabled signal grounded")
    e3 = evidence_set([_item("a", flows_to=["b"]), _item("b")])
    if bound(e3, causal_graph(e3, _method(["dataflow"]), [])) != {"outside_evidence": [], "invisible_to_method": []}:
        bad.append("bound must be empty-but-stated when fully grounded")
    e4 = evidence_set([_item("a", flows_to=["b"], controls=["b"], changed_with=["b"], precedes=["b"]), _item("b")])
    if bound(e4, causal_graph(e4, _method([]), []))["invisible_to_method"] != [{"cause": "a", "effect": "b"}] * 4:
        bad.append("bound must track every relation kind invisible to the method")
    return bad


def _probe_design_root():
    bad = []
    if terminus_is_design_root(_item("a", category="unbounded-input")) is not True:
        bad.append("terminus_is_design_root must hold when a category is named")
    if terminus_is_design_root(_item("a")) is not False:
        bad.append("terminus_is_design_root must not hold without a category")
    return bad


def _probe_attest():
    bad = []
    e = evidence_set([_item("b", flows_to=["a"]), _item("a")])
    graph = causal_graph(e, _method(["dataflow"]), [])
    chain = trace(graph, _symptom("a"))
    att = attest(_symptom("a"), e, _method(["dataflow"]), graph, chain, "")
    expected = {
        "symptom": "s",
        "evidence_hash": e["hash"],
        "method_version": "m1",
        "terminus": "b",
        "chain": ["a", "b"],
        "marked_edges": [],
        "bound": {"outside_evidence": [], "invisible_to_method": []},
        "category": "",
        "poka_yoke": "",
    }
    if att != expected:
        bad.append(f"attest must assemble the negative statement: {att}")
    j = causal_edge("root", "a", "judgment")
    e2 = evidence_set([_item("root", category="unowned-mutation"), _item("a")])
    g2 = causal_graph(e2, _method(["dataflow", "judgment"]), [j])
    att2 = attest(_symptom("a"), e2, _method(["dataflow", "judgment"]), g2, trace(g2, _symptom("a")), "poka-yoke.md")
    if att2["terminus"] != "root" or att2["marked_edges"] != [j] or att2["category"] != "unowned-mutation" or att2["poka_yoke"] != "poka-yoke.md":
        bad.append(f"attest must carry marked edges and the design-root category: {att2}")
    # a symptom site that is not an evidence item -> no terminus item -> empty category
    ghost = evidence_set([_item("a")])
    att3 = attest(_symptom("ghost"), ghost, _method(["dataflow"]), causal_graph(ghost, _method(["dataflow"]), []), ["ghost"], "")
    if att3["terminus"] != "ghost" or att3["category"] != "":
        bad.append(f"attest must leave category empty when the terminus is not an evidence item: {att3}")
    return bad


def _good():
    return {
        "symptom": "s",
        "evidence_hash": "h",
        "method_version": "m1",
        "terminus": "x",
        "chain": ["a", "x"],
        "marked_edges": [],
        "bound": {"outside_evidence": [], "invisible_to_method": []},
        "category": "",
        "poka_yoke": "",
    }


def _probe_validate():
    bad = []
    if validate_attestation(_good()) != []:
        bad.append("validate must accept a well-formed attestation")
    cases = [
        (_good() | {"evidence_hash": ""}, "missing_evidence_hash"),
        (_good() | {"method_version": ""}, "missing_method_version"),
        (_good() | {"terminus": ""}, "missing_terminus"),
        ({k: v for k, v in _good().items() if k != "bound"}, "missing_bound"),
        (_good() | {"category": "unbounded-input", "poka_yoke": ""}, "missing_poka_yoke"),
    ]
    for att, code in cases:
        faults = validate_attestation(att)
        if [fault["code"] for fault in faults] != [code]:
            bad.append(f"validate must fault {code}: got {[fault['code'] for fault in faults]}")
        elif not faults[0]["message"] or faults[0]["category"] != "server":
            bad.append(f"validate fault {code} must carry a non-empty message and the server category")
    if validate_attestation(_good() | {"category": "unbounded-input", "poka_yoke": "poka-yoke.md"}) != []:
        bad.append("validate must accept a design root with a poka-yoke")
    return bad


def _probe_public_surface():
    return (
        []
        if honest_rca.__all__ == [
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
        else [f"__all__ drifted: {honest_rca.__all__}"]
    )


def _probe_vocabularies():
    bad = []
    if EVIDENCE_KINDS != ("code", "event", "history", "config", "deploy"):
        bad.append("EVIDENCE_KINDS drifted")
    if SIGNAL_KINDS != ("dataflow", "controlflow", "change_correlation", "temporal", "judgment"):
        bad.append("SIGNAL_KINDS drifted")
    if DETERMINISTIC_SIGNALS != ("dataflow", "controlflow", "change_correlation", "temporal"):
        bad.append("DETERMINISTIC_SIGNALS drifted")
    if BOUND_KINDS != ("outside_evidence", "invisible_to_method"):
        bad.append("BOUND_KINDS drifted")
    if RELATION_SIGNAL != {"flows_to": "dataflow", "controls": "controlflow", "changed_with": "change_correlation", "precedes": "temporal"}:
        bad.append("RELATION_SIGNAL drifted")
    return bad


def run():
    probes = {
        "evidence": _probe_evidence(),
        "edges": _probe_edges(),
        "graph": _probe_graph(),
        "trace": _probe_trace(),
        "bound": _probe_bound(),
        "design_root": _probe_design_root(),
        "attest": _probe_attest(),
        "validate": _probe_validate(),
        "evidence_kinds": _probe_evidence_kinds(),
        "reproducibility": _probe_reproducibility(),
        "no_positive_claim": _probe_no_positive_claim(),
        "vocabularies": _probe_vocabularies(),
        "public_surface": _probe_public_surface(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HR-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HR laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
