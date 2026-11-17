"""honest-test conformance: build_proof_event — the hf.proof.checked record.

build_proof_event(function_name, scenario, cases_run, outcome, line_coverage,
branch_coverage) builds one ProofEvent per proven function (spec §8.5): the fully-
qualified name, the gherkin scenario, how many cases ran, the proved-or-failed
outcome, and the line and branch coverage. This probe asserts every field reaches
the record unchanged, for both the proved and the failed outcome.

No classes, no mocks. It calls the real honest_test.build_proof_event.
"""

from honest_test import build_proof_event


def _check(function_name, scenario, cases_run, outcome, line_coverage, branch_coverage):
    bad = []
    got = build_proof_event(function_name, scenario, cases_run, outcome, line_coverage, branch_coverage)
    if not isinstance(got, dict):
        return [f"build_proof_event returned {got!r}, expected a ProofEvent dict"]
    want = {
        "function_name": function_name,
        "scenario": scenario,
        "cases_run": cases_run,
        "outcome": outcome,
        "line_coverage": line_coverage,
        "branch_coverage": branch_coverage,
    }
    for name, value in want.items():
        if got.get(name) != value:
            bad.append(f"build_proof_event.{name} = {got.get(name)!r}, expected {value!r}")
    return bad


def probe_build_proof_event():
    bad = []
    bad += _check("honest_type.classify", "classify sorts a token into its slot", 42, "proved", 100, 100)
    bad += _check("honest_type.bind", "bind rejects an unknown slot", 7, "failed", 95, 88)
    return bad


def run():
    messages = probe_build_proof_event()
    if messages:
        print(f"FAIL HTEST-probe [build_proof_event]: {messages}")
    print(f"build_proof_event: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
