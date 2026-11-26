# scenario: run_source_mutation returns a fault for malformed source
# inherits: hd=python/honest-test/honest-test.hd::run_source_mutation -> feature=specs/features/honest-test.feature::run_source_mutation returns a fault for malformed source
"""Verify that run_source_mutation returns a fault for malformed source."""


def probe_run_source_mutation_malformed():
    try:
        from honest_test.analyze import run_source_mutation
    except ImportError as exc:
        return [f"cannot import run_source_mutation: {exc}"]

    got = run_source_mutation("def broken(:\n")
    if not isinstance(got, dict) or got.keys() != {"problem", "remedy"}:
        return [f"run_source_mutation returned {got!r}, expected a Fault"]
    if "parse" not in got["problem"] or "fix" not in got["remedy"]:
        return [f"run_source_mutation returned {got!r}, expected parse failure with a correction"]
    return []



def run():
    failures = probe_run_source_mutation_malformed()
    for failure in failures:
        print(f"FAIL probe_run_source_mutation_malformed: {failure}")
    return len(failures)
