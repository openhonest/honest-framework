# scenario: idempotency_findings reports different answers
# inherits: hd=python/honest-test/honest-test.hd::idempotency_findings -> feature=specs/features/honest-test.feature::idempotency_findings reports different answers
"""Verify that idempotency_findings reports different answers."""


def probe_idempotency_findings_different():
    try:
        from honest_test.honesty import idempotency_findings
    except ImportError as exc:
        return [f"cannot import idempotency_findings: {exc}"]

    got = idempotency_findings(1, 2)
    actual = [(finding["kind"], finding["code"]) for finding in got]
    expected = [("failure", "not_idempotent")]
    if actual != expected:
        return [f"idempotency_findings returned {actual!r}, expected {expected!r}"]
    message = got[0]["message"].casefold()
    if not all(term in message for term in ('different', 'identical input')):
        return [f"the finding should explain that identical inputs produced different results: {got!r}"]
    return []



def run():
    failures = probe_idempotency_findings_different()
    for failure in failures:
        print(f"FAIL probe_idempotency_findings_different: {failure}")
    return len(failures)
