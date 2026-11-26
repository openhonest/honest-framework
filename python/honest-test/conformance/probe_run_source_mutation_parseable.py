# scenario: run_source_mutation returns mutants for parseable source
# inherits: hd=python/honest-test/honest-test.hd::run_source_mutation -> feature=specs/features/honest-test.feature::run_source_mutation returns mutants for parseable source
"""Verify that run_source_mutation returns mutants for parseable source."""


def probe_run_source_mutation_parseable():
    try:
        from honest_test.analyze import run_source_mutation
    except ImportError as exc:
        return [f"cannot import run_source_mutation: {exc}"]

    got = run_source_mutation("value = 2\n")
    expected = {
        "change_kind": "number_shift", "original": "2", "replacement": "3",
        "location": "Point(row=0, column=8)-Point(row=0, column=9)",
    }
    if expected not in got:
        return [f"run_source_mutation returned {got!r}, missing the declared number shift {expected!r}"]
    return []



def run():
    failures = probe_run_source_mutation_parseable()
    for failure in failures:
        print(f"FAIL probe_run_source_mutation_parseable: {failure}")
    return len(failures)
