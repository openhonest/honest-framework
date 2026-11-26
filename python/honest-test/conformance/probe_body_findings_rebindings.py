# scenario: body_findings reports one rejection per runtime rebinding
# inherits: hd=python/honest-test/honest-test.hd::body_findings -> feature=specs/features/honest-test.feature::body_findings reports one rejection per runtime rebinding
"""Verify that body_findings reports one rejection per runtime rebinding."""


def probe_body_findings_rebindings():
    try:
        from honest_test.honesty import body_findings
    except ImportError as exc:
        return [f"cannot import body_findings: {exc}"]

    from honest_parse import parse

    source = (
        b'import target\n\ndef test_one(monkeypatch):\n'
        b'    monkeypatch.setattr(target, "run", lambda: 1)\n'
        b'    value = 2\n'
        b'    target.run = lambda: 3\n'
        b'    monkeypatch.setitem(target.handlers, "run", lambda: 4)\n'
        b'    monkeypatch.delattr(target, "run")\n'
        b'    monkeypatch.setenv("TARGET_MODE", "fake")\n'
        b'    setattr(target, "run", lambda: 5)\n'
        b'    with mock.patch("target.run", return_value=6): pass\n'
        b'    delattr(target, "run")\n'
        b'\ndef broken(:\n'
    )
    root = parse(source, "python").root_node
    findings = body_findings(root)
    actual = [
        (
            row["kind"], row["code"], row["location"],
            "pass the dependency as a parameter" in row["message"]
            or "inject a boundary plug" in row["message"],
        )
        for row in findings
    ]
    expected = [
        ("rejection", "test_body_dishonest", "4:5", True),
        ("rejection", "test_body_dishonest", "7:5", True),
        ("rejection", "test_body_dishonest", "8:5", True),
        ("rejection", "test_body_dishonest", "9:5", True),
        ("rejection", "test_body_dishonest", "10:5", True),
        ("rejection", "test_body_dishonest", "11:10", True),
        ("rejection", "test_body_dishonest", "12:5", True),
        ("rejection", "test_body_dishonest", "6:5", True),
    ]
    if sorted(actual) != sorted(expected):
        return [f"body_findings returned {actual!r}, expected {expected!r}"]
    return []



def run():
    failures = probe_body_findings_rebindings()
    for failure in failures:
        print(f"FAIL probe_body_findings_rebindings: {failure}")
    return len(failures)
