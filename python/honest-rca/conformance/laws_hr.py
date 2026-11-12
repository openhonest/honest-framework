"""honest-rca generative laws (spec sections 3-8, 12).

The suite.json cases pin exact behaviour at representative points. These laws assert the apophatic
invariants over whole vocabularies and over the pipeline: the hash is order-independent and
change-sensitive, every deterministic signal detector grounds its own relation and nothing else,
the graph honours the enabled-signal set, the trace reaches a fixpoint even on a cycle, the bound
always states both modes, every attestation omission yields its fault, a fixed E and M reproduce an
identical attestation, and no attestation carries a positive "X is the root" field. Each law returns
a list of failure strings; run() prints them and returns an exit code.
"""

import honest_rca
from honest_rca import (
    attest,
    bound,
    causal_graph,
    evidence_hash,
    evidence_set,
    signal_edges,
    terminus_is_design_root,
    trace,
    validate_attestation,
)

_SIGNAL_RELATION = {
    "dataflow": "flows_to",
    "controlflow": "controls",
    "change_correlation": "changed_with",
    "temporal": "precedes",
}


def _item(item_id, *, flows_to=None, controls=None, changed_with=None, precedes=None, kind="code", category=""):
    return {
        "id": item_id,
        "kind": kind,
        "ref": f"ref-{item_id}",
        "flows_to": flows_to or [],
        "controls": controls or [],
        "changed_with": changed_with or [],
        "precedes": precedes or [],
        "category": category,
    }


def _item_with_relation(item_id, relation_field, downstream):
    return _item(item_id, **{relation_field: downstream})


def _well_formed_attestation():
    return {
        "symptom": {"id": "s", "description": "d", "site": "c"},
        "evidence_hash": "H1",
        "method_version": "v1",
        "terminus": "a",
        "chain": ["c", "a"],
        "marked_edges": [],
        "bound": {"outside_evidence": [], "invisible_to_method": []},
        "category": "",
        "poka_yoke": "",
    }


def law_evidence_hash_order_independent_and_change_sensitive():
    out = []
    a = _item("a", flows_to=["b"])
    b = _item("b", precedes=["a"])
    if evidence_hash([a, b]) != evidence_hash([b, a]):
        out.append("evidence_hash depends on item order")
    changed = _item("a", flows_to=["z"])
    if evidence_hash([a, b]) == evidence_hash([changed, b]):
        out.append("evidence_hash did not change when an item's relation changed")
    changed_kind = _item("a", flows_to=["b"], kind="event")
    if evidence_hash([a, b]) == evidence_hash([changed_kind, b]):
        out.append("evidence_hash did not change when an item's kind changed")
    return out


def law_each_deterministic_signal_grounds_its_own_relation():
    out = []
    for kind, field in _SIGNAL_RELATION.items():
        present = {"items": [_item_with_relation("a", field, ["b"])], "hash": "h"}
        edges = signal_edges(present, kind)
        want = {("a", "b", kind, False)}
        got = {(e["cause"], e["effect"], e["signal"], e["marked"]) for e in edges}
        if got != want:
            out.append(f"signal_edges(_, {kind!r}) = {got!r}, expected {want!r}")
        absent = {"items": [_item("a")], "hash": "h"}
        if signal_edges(absent, kind) != []:
            out.append(f"signal_edges(_, {kind!r}) grounded an edge from an absent relation")
    return out


def law_causal_graph_honours_enabled_signals():
    out = []
    items = [_item("a", flows_to=["b"], controls=["b"]), _item("b")]
    evidence = {"items": items, "hash": "h"}
    judgment = {"cause": "x", "effect": "a", "signal": "judgment", "marked": True}

    only_dataflow = causal_graph(evidence, {"version": "v", "signals": ["dataflow"], "traversal": "u"}, [judgment])
    signals_built = {e["signal"] for e in only_dataflow["edges"]}
    if signals_built != {"dataflow"}:
        out.append(f"with only dataflow enabled, edge signals = {signals_built!r}, expected just dataflow (no controlflow, no judgment)")

    with_judgment = causal_graph(evidence, {"version": "v", "signals": ["dataflow", "judgment"], "traversal": "u"}, [judgment])
    if not any(e["signal"] == "judgment" and e["marked"] for e in with_judgment["edges"]):
        out.append("judgment enabled but the supplied marked edge was not added")
    return out


def law_trace_reaches_a_fixpoint_even_on_a_cycle():
    out = []
    linear = {
        "nodes": ["a", "b", "c"],
        "edges": [
            {"cause": "a", "effect": "b", "signal": "dataflow", "marked": False},
            {"cause": "b", "effect": "c", "signal": "dataflow", "marked": False},
        ],
    }
    chain = trace(linear, {"id": "s", "description": "d", "site": "c"})
    if chain[0] != "c" or chain[-1] != "a":
        out.append(f"linear trace = {chain!r}, expected to start at the site c and end at the fixpoint a")
    if len(set(chain)) != len(chain):
        out.append(f"linear trace revisited a node: {chain!r}")

    cyclic = {
        "nodes": ["a", "b"],
        "edges": [
            {"cause": "a", "effect": "b", "signal": "dataflow", "marked": False},
            {"cause": "b", "effect": "a", "signal": "dataflow", "marked": False},
        ],
    }
    cyclic_chain = trace(cyclic, {"id": "s", "description": "d", "site": "a"})
    if not cyclic_chain:
        out.append("cyclic trace returned an empty chain")
    if len(set(cyclic_chain)) != len(cyclic_chain):
        out.append(f"cyclic trace revisited a node (did not terminate at the cycle entry): {cyclic_chain!r}")
    return out


def law_bound_always_states_both_modes():
    out = []
    for items, edges in (
        ([_item("a", flows_to=["z"]), _item("b")], []),
        ([_item("a"), _item("b")], []),
    ):
        evidence = {"items": items, "hash": "h"}
        graph = {"nodes": [i["id"] for i in items], "edges": edges}
        result = bound(evidence, graph)
        if set(result.keys()) != {"outside_evidence", "invisible_to_method"}:
            out.append(f"bound keys = {sorted(result.keys())}, expected both modes always stated")
    return out


def law_validate_returns_the_fault_for_each_omission():
    out = []
    cases = (
        (_well_formed_attestation(), []),
        ({**_well_formed_attestation(), "evidence_hash": ""}, ["missing_evidence_hash"]),
        ({**_well_formed_attestation(), "method_version": ""}, ["missing_method_version"]),
        ({**_well_formed_attestation(), "terminus": ""}, ["missing_terminus"]),
        ({**_well_formed_attestation(), "bound": None}, ["missing_bound"]),
        ({**_well_formed_attestation(), "category": "missing_invariant"}, ["missing_poka_yoke"]),
        ({**_well_formed_attestation(), "category": "missing_invariant", "poka_yoke": "pk"}, []),
    )
    for attestation, want in cases:
        codes = sorted(f["code"] for f in validate_attestation(attestation))
        if codes != sorted(want):
            out.append(f"validate_attestation codes = {codes}, expected {sorted(want)} for {attestation.get('category')!r}/{attestation.get('evidence_hash')!r}")
    return out


def law_fixed_evidence_and_method_reproduce_the_attestation():
    """§12: the bounded-completeness invariant — a fixed E and M reproduce an identical attestation."""
    items = [_item("a", flows_to=["b"]), _item("b", flows_to=["c"]), _item("c")]
    method = {"version": "v1", "signals": ["dataflow"], "traversal": "u"}
    symptom = {"id": "s", "description": "d", "site": "c"}

    def produce():
        e = evidence_set(items)
        graph = causal_graph(e, method, [])
        chain = trace(graph, symptom)
        return attest(symptom, e, method, graph, chain, "")

    if produce() != produce():
        return ["a fixed E and M did not reproduce an identical attestation"]
    return []


def law_attestation_carries_no_positive_root_claim():
    """§2, §12: the record has no field that asserts 'X is the root'."""
    items = [_item("a", flows_to=["c"]), _item("c")]
    method = {"version": "v1", "signals": ["dataflow"], "traversal": "u"}
    symptom = {"id": "s", "description": "d", "site": "c"}
    e = evidence_set(items)
    graph = causal_graph(e, method, [])
    chain = trace(graph, symptom)
    attestation = attest(symptom, e, method, graph, chain, "")
    expected_fields = {
        "symptom", "evidence_hash", "method_version", "terminus", "chain",
        "marked_edges", "bound", "category", "poka_yoke",
    }
    if set(attestation.keys()) != expected_fields:
        return [f"attestation fields = {sorted(attestation.keys())}, expected exactly the nine negative-claim fields"]
    return []


def law_terminus_is_design_root_iff_category():
    out = []
    for kind in honest_rca.EVIDENCE_KINDS:
        if terminus_is_design_root(_item("a", kind=kind, category="unbounded_input")) is not True:
            out.append(f"terminus_is_design_root false for a {kind!r} item carrying a category")
        if terminus_is_design_root(_item("a", kind=kind, category="")) is not False:
            out.append(f"terminus_is_design_root true for a {kind!r} item with no category")
    return out


_LAWS = (
    law_evidence_hash_order_independent_and_change_sensitive,
    law_each_deterministic_signal_grounds_its_own_relation,
    law_causal_graph_honours_enabled_signals,
    law_trace_reaches_a_fixpoint_even_on_a_cycle,
    law_bound_always_states_both_modes,
    law_validate_returns_the_fault_for_each_omission,
    law_fixed_evidence_and_method_reproduce_the_attestation,
    law_attestation_carries_no_positive_root_claim,
    law_terminus_is_design_root_iff_category,
)


def run():
    passed = 0
    failed = 0
    for law in _LAWS:
        failures = law()
        if failures:
            failed += 1
            for failure in failures:
                print(f"FAIL {law.__name__}: {failure}")
        else:
            passed += 1
    print(f"laws: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(run())
