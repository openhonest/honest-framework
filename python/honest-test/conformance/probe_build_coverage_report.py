"""honest-test conformance: build_coverage_report — the four-dimension assembler.

build_coverage_report(vocabularies, chains, honesty, state_machines) assembles the
four coverage maps into a CoverageReport and stamps the format version '1.0' (spec
§9.5). This probe asserts the version stamp and that each argument map passes
through unchanged.

No classes, no mocks. It calls the real honest_test.build_coverage_report and reads
the returned record by shape.
"""

from honest_test import build_coverage_report


def probe_build_coverage_report():
    bad = []
    vocabularies = {"format_vocab": {"total": 5, "exercised": 5, "pct": 100}}
    chains = {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}}
    honesty = {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}}
    state_machines = {"order_machine": {"total": 5, "exercised": 4, "pct": 80}}

    got = build_coverage_report(vocabularies, chains, honesty, state_machines)
    if not isinstance(got, dict):
        return [f"build_coverage_report returned {got!r}, expected a CoverageReport dict"]
    if got.get("version") != "1.0":
        bad.append(f"build_coverage_report stamped version {got.get('version')!r}, expected '1.0'")
    if got.get("vocabularies") != vocabularies:
        bad.append(f"vocabularies passed through as {got.get('vocabularies')!r}, expected {vocabularies!r}")
    if got.get("chains") != chains:
        bad.append(f"chains passed through as {got.get('chains')!r}, expected {chains!r}")
    if got.get("honesty") != honesty:
        bad.append(f"honesty passed through as {got.get('honesty')!r}, expected {honesty!r}")
    if got.get("state_machines") != state_machines:
        bad.append(f"state_machines passed through as {got.get('state_machines')!r}, expected {state_machines!r}")
    return bad


def run():
    messages = probe_build_coverage_report()
    if messages:
        print(f"FAIL HTEST-probe [build_coverage_report]: {messages}")
    print(f"build_coverage_report: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
