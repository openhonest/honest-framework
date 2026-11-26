# scenario: mutation_findings reports a changed manifest
# inherits: hd=python/honest-test/honest-test.hd::mutation_findings -> feature=specs/features/honest-test.feature::mutation_findings reports a changed manifest
"""Verify that mutation_findings reports a changed manifest."""


def probe_mutation_findings_changed():
    try:
        from honest_test.honesty import mutation_findings
    except ImportError as exc:
        return [f"cannot import mutation_findings: {exc}"]

    before = {"count": 1}
    after = {"count": 2}
    got = mutation_findings(before, after)
    expected = [("failure", "manifest_mutated", True, True)]
    actual = [
        (finding["kind"], finding["code"], repr(before) in finding["message"], repr(after) in finding["message"])
        for finding in got
    ]
    if actual != expected:
        return [f"mutation_findings returned {got!r}, expected a failure naming both manifests"]
    return []



def run():
    failures = probe_mutation_findings_changed()
    for failure in failures:
        print(f"FAIL probe_mutation_findings_changed: {failure}")
    return len(failures)
