"""honest-test conformance: build_run_report — the finished-report assembler.

build_run_report assembles the measured pieces of one CLI run into a RunReport
(spec §11): the chains, links and vocabularies found, the permutations run and
failures, the adversarial inputs rejected, the CoverageReport, and the mutation
tally. This probe asserts every field reaches the record unchanged.

No classes, no mocks. It calls the real honest_test.build_run_report and reads the
returned record by shape.
"""

from honest_test import build_run_report


def probe_build_run_report():
    bad = []
    coverage = {
        "version": "1.0",
        "vocabularies": {"format_vocab": {"total": 5, "exercised": 5, "pct": 100}},
        "chains": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
        "honesty": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
        "state_machines": {"order_machine": {"total": 5, "exercised": 5, "pct": 100}},
    }
    fields = {
        "chains": 4,
        "links": 12,
        "vocabularies": 6,
        "permutations": 3024,
        "failures": 0,
        "adversarial_rejected": 1003,
        "warnings": 2,
        "coverage": coverage,
        "mutation_caught": 7,
        "mutation_total": 7,
    }

    got = build_run_report(
        fields["chains"],
        fields["links"],
        fields["vocabularies"],
        fields["permutations"],
        fields["failures"],
        fields["adversarial_rejected"],
        fields["warnings"],
        fields["coverage"],
        fields["mutation_caught"],
        fields["mutation_total"],
    )
    if not isinstance(got, dict):
        return [f"build_run_report returned {got!r}, expected a RunReport dict"]
    for name, value in fields.items():
        if got.get(name) != value:
            bad.append(f"build_run_report.{name} = {got.get(name)!r}, expected {value!r}")
    return bad


def run():
    messages = probe_build_run_report()
    if messages:
        print(f"FAIL HTEST-probe [build_run_report]: {messages}")
    print(f"build_run_report: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
