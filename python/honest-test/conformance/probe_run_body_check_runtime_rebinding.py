# scenario: run_body_check reports runtime rebinding in supplied source
# inherits: hd=python/honest-test/honest-test.hd::run_body_check -> feature=specs/features/honest-test.feature::run_body_check reports runtime rebinding in supplied source
"""Verify that run_body_check reports runtime rebinding in supplied source."""


def probe_run_body_check_runtime_rebinding():
    try:
        from honest_test.io_boundary import run_body_check
    except ImportError as exc:
        return [f"cannot import run_body_check: {exc}"]

    source = 'import target\n\ndef test_one():\n    target.run = lambda: 1\n'
    findings = run_body_check(source)
    actual = [
        (row["kind"], row["code"], row["location"], "pass the dependency as a parameter" in row["message"])
        for row in findings
    ]
    expected = [("rejection", "test_body_dishonest", "4:5", True)]
    if actual != expected:
        return [f"run_body_check returned {actual!r}, expected {expected!r}"]
    return []



def run():
    failures = probe_run_body_check_runtime_rebinding()
    for failure in failures:
        print(f"FAIL probe_run_body_check_runtime_rebinding: {failure}")
    return len(failures)
