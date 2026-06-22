"""honest-test conformance: the HTest laws + generator-internal probes (the circle).

honest-test verifies every other module's generators; here it verifies its own. The HTest
laws (honest-conformance-suite.md) are asserted over real vocabularies through verify_laws —
honest-test eating its own law-runner. The probes then drive the generator internals the
JSON example suite cannot reach from data alone: live-function predicate classification, the
length-bound parser's edge operators, the honesty checks' exempt/skip branches, the TOML
load boundary, and the state-machine generators' degenerate-machine and violation-detector
paths (the last via a deliberately non-conformant transition, to prove the detector fires).

The conformance directory is outside the honest-check gate, so it may read files, build
throwing fixtures, and inject a bad dependency to exercise a verifier's failure branch.
"""

import asyncio
import tempfile
from pathlib import Path

from honest_type import binding, fault, link, ok, state_machine, vocabulary

import honest_test.statemachine as sm_module
from honest_test import (
    adversarial_neighbours,
    classify_predicate,
    classify_source,
    enumerate_sets,
    law,
    load_config,
    supplied_for,
    test_chain_contracts,
    test_invalid_transitions,
    test_valid_transitions,
    verify_idempotency,
    verify_laws,
)
from honest_test.length import _bound_from_pair, enumerate_lengths, extract_length_bounds
from honest_test.predicate import _collect_facts, _fact_call
from honest_parse import parse_python, walk

# --------------------------------------------------------------------------- HTest laws

HTEST_SUBJECTS = [
    ("two_sets", vocabulary({"color": {"red", "green"}, "size": {"small", "large"}})),
    ("one_char", vocabulary({"flag": {"a", "b"}})),
    ("singleton", vocabulary({"only": {"x"}})),
]


def _htest1_exhaustive(vocab):
    """Every declared Set member appears in at least one generated case."""
    cases = enumerate_sets(vocab)
    bad = []
    from honest_type.recognizers import is_bounded, members as set_members

    for name, rec in vocab["base_types"].items():
        if not is_bounded(rec):
            continue
        for member in set_members(rec):
            if not any(case.get(name) == member for case in cases):
                bad.append(f"member {member!r} of {name!r} not exercised")
    return bad


def _htest2_declared(vocab):
    """Every value in every generated case is a declared member (or None for Maybe)."""
    from honest_type.recognizers import members as set_members

    declared = {name: set(set_members(rec)) for name, rec in vocab["base_types"].items()}
    bad = []
    for case in enumerate_sets(vocab):
        for name, value in case.items():
            if value is not None and value not in declared.get(name, set()):
                bad.append(f"case bound {name!r}={value!r}, not a declared member")
    return bad


def _htest4_determinism(vocab):
    """Generation is deterministic: same vocabulary, same suite, every time."""
    if enumerate_sets(vocab) != enumerate_sets(vocab):
        return ["enumerate_sets is not deterministic"]
    member = sorted(next(iter(vocab["base_types"].values()))["members"])[0]
    if adversarial_neighbours(member) != adversarial_neighbours(member):
        return ["adversarial_neighbours is not deterministic"]
    return []


def _htest5_rejection(vocab):
    """For every Set member, adversarial neighbours (the rejection inputs) are generated."""
    from honest_type.recognizers import members as set_members

    bad = []
    for rec in vocab["base_types"].values():
        for member in set_members(rec):
            if not adversarial_neighbours(member):
                bad.append(f"no adversarial neighbours generated for {member!r}")
    return bad


HTEST_LAWS = [
    law("HTest-1", "every declared Set member is exercised by a generated case", _htest1_exhaustive),
    law("HTest-2", "no generated case asserts an undeclared value", _htest2_declared),
    law("HTest-4", "generation is deterministic", _htest4_determinism),
    law("HTest-5", "rejection inputs are generated for every member", _htest5_rejection),
]


# --------------------------------------------------------------------------- fixtures

_format_vocab = vocabulary({"fmt": {"currency", "number"}})


@link(accepts=_format_vocab, binds=binding({"fmt": "format"}))
def _emit_fail(manifest):
    return {"err": fault("emit_failed", "producer faulted", "server")}


@link(boundary=True)
def _boundary(manifest):
    return ok(manifest)


def _always_ok(manifest):
    return ok(manifest)


def _ok_consumer(manifest):
    return ok(manifest)


# --------------------------------------------------------------------------- probes


def _probe_predicate():
    bad = []
    expectations = {
        "def p(s): return str(s) == s": "unknown",       # ignored builtin (59->exit)
        "def p(s): return s.strip() == s": "unknown",    # non-charclass attribute (65->exit)
        "def p(s): return fns[0](s)": "unknown",         # subscript callee (77->exit)
    }
    for source, expect in expectations.items():
        got = classify_source(source)
        if got != expect:
            bad.append(f"classify_source({source!r}) = {got}, expected {expect}")
    if classify_predicate(lambda s: s.isdigit()) != "character_class":
        bad.append("classify_predicate on a live readable fn failed")
    if classify_predicate(len) != "external":
        bad.append("classify_predicate on a C builtin should fall back to external")
    # callee-is-None guard: feed _fact_call a non-call node (an integer has no function field).
    facts = _collect_facts("0")
    integer_node = next(n for n in walk(parse_python(b"0").root_node) if n.type == "integer")
    _fact_call(integer_node, b"0", facts)  # must return without error (line 75)
    return bad


def _probe_length():
    bad = []
    if extract_length_bounds("def p(s): return len(s) is not None is not False") != (1, None):
        bad.append("is-not chain should contribute no bound")
    if extract_length_bounds('def p(s): return len(s) >= 3 and "a" < "b"') != (3, None):
        bad.append("non-len comparison should be ignored")
    below = enumerate_lengths("def p(s): return len(s) < 0")
    if below["valid"] or below["invalid"] != [""]:
        bad.append(f"len(s) < 0 should yield empty valid and a zero-length invalid: {below}")
    # The op-not-in-bound guard is unreachable from the scanner (the operator sets coincide);
    # probe it directly to document the contract.
    bounds = {"min": 1, "max": None}
    _bound_from_pair(None, "!=", None, b"", bounds)
    if bounds != {"min": 1, "max": None}:
        bad.append("an unknown comparison operator must contribute no bound")
    return bad


def _probe_honesty():
    bad = []
    if verify_idempotency([_boundary], {"a": 1}) is not None:
        bad.append("a chain with a boundary link is exempt from idempotency")
    if test_chain_contracts([_always_ok, _ok_consumer]):
        bad.append("a producer with no accepts vocabulary contributes no contract cases")
    if test_chain_contracts([_emit_fail, _ok_consumer]):
        bad.append("a producer that faults yields no contract violation")
    return bad


def _probe_supplied():
    bad = []
    if load_config("/no/such/honest-test.toml") != {}:
        bad.append("load_config of a missing file should be {}")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "honest-test.toml"
        path.write_text('[predicates.customer_id]\nvalid = ["C1"]\nstrategy = "supplied_only"\n', encoding="utf-8")
        config = load_config(str(path))
        entry = supplied_for(config, "customer_id")
        if entry is None or entry["valid"] != ["C1"]:
            bad.append(f"load_config did not parse the TOML file: {config}")
    return bad


def _probe_statemachine():
    bad = []
    # Degenerate machines: empty events and empty states each skip one adversarial loop.
    no_events = state_machine({"a"}, set(), {}, "a")
    if sm_module.test_adversarial_transitions(no_events):
        bad.append("an events-less machine should yield no adversarial findings")
    empty_states = {"states": set(), "events": {"e"}, "transitions": {}, "initial": None, "terminal": []}
    if sm_module.test_adversarial_transitions(empty_states):
        bad.append("a states-less machine should yield no adversarial findings")
    # A table entry from an unknown state: test_valid must flag the incorrect transition.
    ghost = {"states": {"a"}, "events": {"e"}, "transitions": {("ghost", "e"): "a"}, "initial": "a", "terminal": []}
    if len(test_valid_transitions(ghost)) != 1:
        bad.append("a transition from an unknown state must be flagged incorrect")
    # The invalid-transition detector only fires against a non-conformant transition(); inject
    # one that wrongly accepts every pair, and prove the detector catches it.
    machine = state_machine({"a", "b"}, {"e"}, {("a", "e"): "a"}, "a")
    saved = sm_module.transition
    sm_module.transition = lambda m, s, e: ok({"state": "a"})
    try:
        if not test_invalid_transitions(machine):
            bad.append("the no_transition detector failed to catch a wrongly-accepted pair")
    finally:
        sm_module.transition = saved
    # Overlapping events: a neighbour of one event is itself a declared event, so the
    # adversarial-event detector must flag it (the symmetric event path).
    overlap = state_machine({"a"}, {"go", "GO"}, {("a", "go"): "a"}, "a")
    if not sm_module.test_adversarial_transitions(overlap):
        bad.append("an event whose neighbour is also a declared event must be flagged")
    return bad


def _probe_runner():
    """verify_laws must report a violation when a law fails (the runner's failure path)."""
    bad = []
    report = verify_laws([law("DEMO", "always fails", lambda subject: ["intentional"])], [("s", None)])
    if report["failed"] != 1 or not report["violations"]:
        bad.append(f"verify_laws did not record a failing law: {report}")
    if report["violations"] and report["violations"][0]["messages"] != ["intentional"]:
        bad.append("verify_laws did not carry the violation messages")
    return bad


def _probe_proof():
    """Proof events (§8.5): the pure payload, and the injected-emit loop that writes one
    hf.proof.checked per function (and nothing for an empty run)."""
    from honest_test import PROOF_RESULTS, emit_proofs, proof_payload

    async def _run():
        bad = []
        if PROOF_RESULTS != {"proved", "failed"}:
            bad.append("PROOF_RESULTS vocabulary is wrong")
        payload = proof_payload("m.f", "f does x", "m", 3, "proved", [], 100.0, 100.0)
        if payload["function"] != "m.f" or payload["result"] != "proved" or payload["branch_coverage"] != 100.0:
            bad.append(f"proof_payload wrong: {payload}")

        calls = []

        async def emit(event_type, aggregate_type, aggregate_id, event_payload):
            calls.append((event_type, aggregate_type, aggregate_id, event_payload))
            return {"ok": {"event_id": "e"}}

        proofs = [
            {"function": "m.a", "gherkin": "a", "module": "m", "cases": 1, "result": "proved", "failures": [], "line_coverage": 100.0, "branch_coverage": 100.0},
            {"function": "m.b", "gherkin": "b", "module": "m", "cases": 2, "result": "failed", "failures": ["x"], "line_coverage": 50.0, "branch_coverage": 0.0},
        ]
        results = await emit_proofs(emit, proofs)
        if len(calls) != 2 or len(results) != 2:
            bad.append(f"emit_proofs should emit once per proof: {calls}")
        elif calls[0][:3] != ("hf.proof.checked", "function", "m.a") or calls[1][2] != "m.b" or calls[1][3]["result"] != "failed":
            bad.append(f"emit_proofs emitted the wrong event/aggregate/payload: {calls}")
        if await emit_proofs(emit, []) != [] or len(calls) != 2:
            bad.append("an empty run should emit nothing")
        return bad

    return asyncio.run(_run())


def run():
    report = verify_laws(HTEST_LAWS, HTEST_SUBJECTS)
    probes = {
        "predicate": _probe_predicate(),
        "length": _probe_length(),
        "honesty": _probe_honesty(),
        "supplied": _probe_supplied(),
        "statemachine": _probe_statemachine(),
        "runner": _probe_runner(),
        "proof": _probe_proof(),
    }
    violations = list(report["violations"])
    for name, messages in probes.items():
        if messages:
            violations.append({"law": "HTest-probe", "statement": name, "subject": name, "messages": messages})

    probe_total = len(probes)
    probe_passed = sum(1 for m in probes.values() if not m)
    passed = report["passed"] + probe_passed
    total = report["total"] + probe_total

    for v in violations:
        print(f"FAIL {v['law']} [{v['subject']}]: {v['messages']}")
    print(f"HTest laws: {passed} passed, {len(violations)} failed, {total} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
