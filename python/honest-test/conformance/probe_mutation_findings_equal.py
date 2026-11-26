# scenario: mutation_findings returns no finding for equal manifests
# inherits: hd=python/honest-test/honest-test.hd::mutation_findings -> feature=specs/features/honest-test.feature::mutation_findings returns no finding for equal manifests
"""Verify that mutation_findings returns no finding for equal manifests."""


def probe_mutation_findings_equal():
    try:
        from honest_test.honesty import mutation_findings
    except ImportError as exc:
        return [f"cannot import mutation_findings: {exc}"]

    got = mutation_findings({"count": 1}, {"count": 1})
    if got != []:
        return [f"mutation_findings returned {got!r}, expected []"]
    return []



def run():
    failures = probe_mutation_findings_equal()
    for failure in failures:
        print(f"FAIL probe_mutation_findings_equal: {failure}")
    return len(failures)
