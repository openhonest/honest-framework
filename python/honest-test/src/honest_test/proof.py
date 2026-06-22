"""Proof events (section 8.5): honest-test's verification results into the event log.

A conformance run emits one `hf.proof.checked` event per function (honest-observe §4.8), keyed by
the function's fully-qualified name — which is its one gherkin and its function-point unit. The
event is written through an INJECTED emit; this module never imports honest-observe, so the
dependency runs one way (test -> observe, only when a runtime is wired in at the run boundary).

`proof_payload` builds the payload (pure); `emit_proofs` emits one event per function proof
through the injected emit (I/O via that callable only). `decide_proof` is the pure rule for what
earns `proved`. The closed result vocabulary is `PROOF_RESULTS`.
"""

PROOF_RESULTS = frozenset({"proved", "failed"})


def decide_proof(honesty_ok, coverage_ok, value_results, exempt=False):
    """Decide a function's proof result (section 8.5). A function is `proved` only when all three
    legs hold together: the honesty checks pass, it is fully covered, and its value oracle ran and
    every case passed. An unrun oracle is not a pass — an unchecked value can be silently wrong,
    which is the bug the value oracle exists to catch — so an empty `value_results` is a failure,
    not a vacuous proof.

    `exempt` waives the value-oracle leg only — never honesty or coverage — for a function a value
    oracle cannot cover by nature: its output is not expressible as a portable value (a combinatorial
    generator, a tuple), so its correctness is carried by the property laws instead. The exemption is
    declared explicitly per function (auditable), never inferred. Returns {result, failures};
    `failures` names every missing leg. Pure."""
    failures = []
    if not honesty_ok:
        failures.append("honesty checks did not pass")
    if not coverage_ok:
        failures.append("not fully covered (line or branch below 100%)")
    if not exempt and not value_results:
        failures.append("no value oracle: the function's Then is not yet checked by a value case")
    failures.extend(f"value case {result['id']!r}: {result['fault']['detail']}" for result in value_results if not result["proved"])
    return {"result": "proved" if not failures else "failed", "failures": failures}


def proof_payload(function, gherkin, module, cases, result, failures, line_coverage, branch_coverage):
    """The hf.proof.checked payload for one function (honest-observe §4.8). Pure. `result` is a
    member of PROOF_RESULTS; `failures` is empty unless `result` is "failed"."""
    return {
        "function": function,
        "gherkin": gherkin,
        "module": module,
        "cases": cases,
        "result": result,
        "failures": failures,
        "line_coverage": line_coverage,
        "branch_coverage": branch_coverage,
    }


async def emit_proofs(emit, proofs):
    """Emit one hf.proof.checked per function proof through the injected `emit` (section 8.5). Each
    proof is the keyword set for proof_payload. I/O — through `emit` only. Returns the emit results
    in order; an empty run emits nothing."""
    results = []
    for proof in proofs:
        results.append(await emit("hf.proof.checked", "function", proof["function"], proof_payload(**proof)))
    return results
