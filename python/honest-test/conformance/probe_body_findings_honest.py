# scenario: body_findings returns empty for an honest test body
# inherits: hd=python/honest-test/honest-test.hd::body_findings -> feature=specs/features/honest-test.feature::body_findings returns empty for an honest test body
"""Verify that body_findings returns empty for an honest test body."""


def probe_body_findings_honest():
    try:
        from honest_test.honesty import body_findings
    except ImportError as exc:
        return [f"cannot import body_findings: {exc}"]

    from honest_parse import parse

    tree = parse(
        b"import operator\n"
        b"def test_one():\n"
        b"    entries = {}\n"
        b"    operator.setitem(entries, 'count', 1)\n"
        b"    assert entries.get('count') == 1\n",
        "python",
    )
    findings = body_findings(tree.root_node)
    if findings != []:
        return [f"body_findings returned {findings!r}, expected []"]
    return []



def run():
    failures = probe_body_findings_honest()
    for failure in failures:
        print(f"FAIL probe_body_findings_honest: {failure}")
    return len(failures)
