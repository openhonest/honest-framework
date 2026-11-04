"""Conformance fragment for the build_proof_event scenario (honest-test.feature).

Scenario: build_proof_event builds one hf.proof.checked event for a function
  honest-test proved.
  Then it returns a ProofEvent record for the host runner to emit through an
  injected honest-observe runtime, so honest-test's core takes no dependency on
  honest-observe.
  And function_name is the fully-qualified name that is the function's gherkin
  requirement and its function-point unit.
  And a function earns outcome proved only when honesty, full coverage and the
  gherkin's Then value oracle all hold; a run where any does not emits failed.
  And it reads no world and returns pure data.

build_proof_event is a pure assembler: it wires its six inputs into the six
named fields of a ProofEvent. Cases are data; one pure probe feeds them to the
real honest_test.build_proof_event and returns a list of failure strings (empty
when every case holds). No classes, no mocks.

Each row gives all six inputs with distinct, recognizable values and spells out
the exact ProofEvent dict expected, so a stub returning {} cannot pass and a
field swap (e.g. line_coverage into branch_coverage) is caught. One row carries
outcome "proved" with full coverage; the other carries outcome "failed" with
distinct partial coverage numbers.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import build_proof_event

_CASES = [
    # A proved function: all six inputs distinct, full coverage.
    {
        "given": {
            "function_name": "honest_type.classify",
            "scenario": "classify sorts tokens",
            "cases_run": 3000,
            "outcome": "proved",
            "line_coverage": 100,
            "branch_coverage": 100,
        },
        "expect": {
            "function_name": "honest_type.classify",
            "scenario": "classify sorts tokens",
            "cases_run": 3000,
            "outcome": "proved",
            "line_coverage": 100,
            "branch_coverage": 100,
        },
    },
    # A failed function: different outcome and two distinct partial coverages so
    # a line/branch field swap is caught.
    {
        "given": {
            "function_name": "honest_persist.apply_diff",
            "scenario": "apply_diff migrates the schema",
            "cases_run": 42,
            "outcome": "failed",
            "line_coverage": 87,
            "branch_coverage": 73,
        },
        "expect": {
            "function_name": "honest_persist.apply_diff",
            "scenario": "apply_diff migrates the schema",
            "cases_run": 42,
            "outcome": "failed",
            "line_coverage": 87,
            "branch_coverage": 73,
        },
    },
]


def probe_build_proof_event():
    """build_proof_event wires its six inputs into the six named fields of the ProofEvent it returns, carrying both outcomes and distinct coverage numbers unchanged."""
    bad = []
    for case in _CASES:
        got = build_proof_event(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"build_proof_event({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_build_proof_event()
    for line in bad:
        print(line)
    print(f"probe_build_proof_event: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
