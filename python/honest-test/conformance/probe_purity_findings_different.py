# scenario: purity_findings reports different answers
# inherits: hd=python/honest-test/honest-test.hd::purity_findings -> feature=specs/features/honest-test.feature::purity_findings reports different answers
"""Verify that purity_findings reports different answers."""


def probe_purity_findings_different():
    try:
        from honest_test.honesty import purity_findings
    except ImportError as exc:
        return [f"cannot import purity_findings: {exc}"]

    got = purity_findings(1, 2)
    actual = [(finding["kind"], finding["code"]) for finding in got]
    expected = [("failure", "non_deterministic")]
    if actual != expected:
        return [f"purity_findings returned {actual!r}, expected {expected!r}"]
    message = got[0]["message"].casefold()
    if not all(term in message for term in ('different', 'identical input')):
        return [f"the finding should explain that identical inputs produced different results: {got!r}"]
    return []



def run():
    failures = probe_purity_findings_different()
    for failure in failures:
        print(f"FAIL probe_purity_findings_different: {failure}")
    return len(failures)
