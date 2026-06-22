"""Proof events (section 8.5): honest-test's verification results into the event log.

A conformance run emits one `hf.proof.checked` event per function (honest-observe §4.8), keyed by
the function's fully-qualified name — which is its one gherkin and its function-point unit. The
event is written through an INJECTED emit; this module never imports honest-observe, so the
dependency runs one way (test -> observe, only when a runtime is wired in at the run boundary).

`proof_payload` builds the payload (pure); `emit_proofs` emits one event per function proof
through the injected emit (I/O via that callable only). The closed result vocabulary is
`PROOF_RESULTS`.
"""

PROOF_RESULTS = frozenset({"proved", "failed"})


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
