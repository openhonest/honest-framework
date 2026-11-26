# scenario: idempotency_findings returns no finding for equal answers
# inherits: hd=python/honest-test/honest-test.hd::idempotency_findings -> feature=specs/features/honest-test.feature::idempotency_findings returns no finding for equal answers
"""Verify that idempotency_findings returns no finding for equal answers."""


def probe_idempotency_findings_equal():
    try:
        from honest_test.honesty import idempotency_findings
    except ImportError as exc:
        return [f"cannot import idempotency_findings: {exc}"]

    got = idempotency_findings(1, 1)
    if got != []:
        return [f"idempotency_findings returned {got!r}, expected []"]
    return []



def run():
    failures = probe_idempotency_findings_equal()
    for failure in failures:
        print(f"FAIL probe_idempotency_findings_equal: {failure}")
    return len(failures)
