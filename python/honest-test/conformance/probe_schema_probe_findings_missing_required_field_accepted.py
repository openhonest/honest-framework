# scenario: schema_probe_findings interprets missing_required_field_accepted
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets missing_required_field_accepted

from honest_test.persist_components import schema_probe_findings


def probe_schema_probe_findings_missing_required_field_accepted():
    findings = schema_probe_findings(table="widgets", outcome="missing_required_field_accepted")
    if not isinstance(findings, list) or len(findings) != 1:
        return [f"got {findings!r}, expected one Finding"]
    finding = findings[0]
    expected = {"kind": "failure", "code": "missing_required_field_accepted", "location": ""}
    actual = {field: finding.get(field) for field in expected}
    message = finding.get("message")
    if actual != expected:
        return [f"got {actual!r}, expected {expected!r}"]
    if not isinstance(message, str):
        return [f"got {message!r}, expected a message naming the table and contract"]
    normalized = message.casefold().replace("-", " ")
    if "widgets" not in normalized or not any(
        term in normalized for term in ('required field', 'required column', 'non nullable')
    ):
        return [f"message {message!r} did not identify widgets and the missing required field accepted contract"]
    return []


def run():
    failures = probe_schema_probe_findings_missing_required_field_accepted()
    for failure in failures:
        print(f"FAIL schema_probe_findings interprets missing_required_field_accepted: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
