# scenario: purity_findings returns no finding for equal answers
# inherits: hd=python/honest-test/honest-test.hd::purity_findings -> feature=specs/features/honest-test.feature::purity_findings returns no finding for equal answers
"""Verify that purity_findings returns no finding for equal answers."""


def probe_purity_findings_equal():
    try:
        from honest_test.honesty import purity_findings
    except ImportError as exc:
        return [f"cannot import purity_findings: {exc}"]

    got = purity_findings(1, 1)
    if got != []:
        return [f"purity_findings returned {got!r}, expected []"]
    return []



def run():
    failures = probe_purity_findings_equal()
    for failure in failures:
        print(f"FAIL probe_purity_findings_equal: {failure}")
    return len(failures)
