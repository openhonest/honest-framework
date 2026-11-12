"""honest-rca conformance runner (spec sections 2-8, 12).

Each case is data: a `kind` discriminator names its checker, and the matching `_check_*` drives the
real function and compares against the expected value. The suite pins exact behaviour at
representative points; the apophatic invariants (hash order-independence, every signal detector over
evidence with and without its relation, the fixpoint on cyclic graphs, every attestation omission and
its fault, and the bounded-completeness reproducibility invariant) are in laws_hr.py.

  uv run --package honest-rca python honest-rca/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

import honest_rca
from honest_rca import (
    attest,
    bound,
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

_PUBLIC = (
    "evidence_hash", "evidence_set", "signal_edges", "causal_graph", "trace",
    "terminus", "bound", "attest", "validate_attestation", "terminus_is_design_root",
    "EVIDENCE_KINDS", "SIGNAL_KINDS", "BOUND_KINDS",
)

_RELATION_FNS = {
    "relation_flows_to": relation_flows_to,
    "relation_controls": relation_controls,
    "relation_changed_with": relation_changed_with,
    "relation_precedes": relation_precedes,
}


def _edge_set(edges):
    return {(e["cause"], e["effect"], e["signal"], e["marked"]) for e in edges}


def _check_vocab(case):
    actual = getattr(honest_rca, case["vocab"], None)
    expect = frozenset(case["expect_members"])
    if not isinstance(actual, frozenset):
        return False, f"{case['vocab']} is {type(actual).__name__}, expected frozenset"
    return actual == expect, f"{case['vocab']} = {actual!r}, expected {expect!r}"


def _check_exports(case):
    missing = [name for name in case["expect_names"] if not hasattr(honest_rca, name)]
    return not missing, f"not importable from honest_rca: {missing}"


def _check_evidence_set(case):
    result = evidence_set(case["items"])
    if result["items"] != case["items"]:
        return False, f"items = {result['items']!r}, expected the given items unchanged"
    if result["hash"] != evidence_hash(case["items"]):
        return False, f"hash = {result['hash']!r}, expected evidence_hash(items)"
    return True, "ok"


def _check_relation(case):
    result = _RELATION_FNS[case["fn"]](case["item"])
    return result == case["expect"], f"{case['fn']} = {result!r}, expected {case['expect']!r}"


def _check_signal_edges(case):
    evidence = {"items": case["items"], "hash": "h"}
    result = signal_edges(evidence, case["signal_kind"])
    want = {(e["cause"], e["effect"], e["signal"], e["marked"]) for e in case["expect_edges"]}
    if _edge_set(result) != want:
        return False, f"edges = {_edge_set(result)!r}, expected {want!r}"
    for edge in result:
        if edge["signal"] != case["signal_kind"] or edge["marked"] is not False:
            return False, f"a grounded edge has signal/marked {edge['signal']!r}/{edge['marked']!r}"
    return True, "ok"


def _check_causal_graph(case):
    evidence = {"items": case["items"], "hash": "h"}
    graph = causal_graph(evidence, case["method"], case.get("judgments", []))
    if set(graph["nodes"]) != set(case["expect_nodes"]):
        return False, f"nodes = {sorted(graph['nodes'])}, expected {sorted(case['expect_nodes'])}"
    want = {tuple(e) for e in case["expect_edges"]}
    got = _edge_set(graph["edges"])
    if got != want:
        return False, f"edges = {got!r}, expected {want!r}"
    return True, "ok"


def _check_trace(case):
    result = trace(case["graph"], case["symptom"])
    return result == case["expect_chain"], f"chain = {result!r}, expected {case['expect_chain']!r}"


def _check_terminus(case):
    result = terminus(case["chain"])
    return result == case["expect"], f"terminus = {result!r}, expected {case['expect']!r}"


def _check_bound(case):
    evidence = {"items": case["items"], "hash": "h"}
    result = bound(evidence, case["graph"])
    if set(result.keys()) != {"outside_evidence", "invisible_to_method"}:
        return False, f"bound keys = {sorted(result.keys())}, expected both BOUND_KINDS always present"
    if sorted(result["outside_evidence"]) != sorted(case["expect_outside"]):
        return False, f"outside_evidence = {sorted(result['outside_evidence'])}, expected {sorted(case['expect_outside'])}"
    return True, "ok"


def _check_attest(case):
    evidence = {"items": case["items"], "hash": case["evidence_hash"]}
    graph = case["graph"]
    result = attest(case["symptom"], evidence, case["method"], graph, case["chain"], case["poka_yoke"])
    checks = {
        "evidence_hash": case["evidence_hash"],
        "method_version": case["method"]["version"],
        "terminus": case["chain"][-1],
        "category": case["expect_category"],
        "poka_yoke": case["poka_yoke"],
    }
    for field, want in checks.items():
        if result[field] != want:
            return False, f"attestation[{field!r}] = {result[field]!r}, expected {want!r}"
    if result["chain"] != case["chain"]:
        return False, f"chain = {result['chain']!r}, expected {case['chain']!r}"
    if set(result["bound"].keys()) != {"outside_evidence", "invisible_to_method"}:
        return False, f"bound not both-keys-present: {result['bound']!r}"
    if "root" in result or "is_root" in result or "cause" in result:
        return False, "attestation carries a positive root-claim field"
    return True, "ok"


def _check_validate(case):
    codes = sorted(f["code"] for f in validate_attestation(case["attestation"]))
    return codes == sorted(case["expect_codes"]), f"fault codes = {codes}, expected {sorted(case['expect_codes'])}"


def _check_design_root(case):
    result = terminus_is_design_root(case["item"])
    return result is case["expect"], f"terminus_is_design_root = {result!r}, expected {case['expect']!r}"


_CHECKERS = {
    "vocab": _check_vocab,
    "exports": _check_exports,
    "evidence_set": _check_evidence_set,
    "relation": _check_relation,
    "signal_edges": _check_signal_edges,
    "causal_graph": _check_causal_graph,
    "trace": _check_trace,
    "terminus": _check_terminus,
    "bound": _check_bound,
    "attest": _check_attest,
    "validate": _check_validate,
    "design_root": _check_design_root,
}


def _kind(case):
    kind = case.get("kind")
    if kind not in _CHECKERS:
        raise ValueError(f"case {case.get('id')!r} names no known kind: {kind!r}")
    return kind


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        if "value_case" in case:
            continue  # value cases are checked centrally by value-check.py; a module cannot run the oracle on itself
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']}: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_hr

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hr.run()
    raise SystemExit(suite_status or laws_status)
