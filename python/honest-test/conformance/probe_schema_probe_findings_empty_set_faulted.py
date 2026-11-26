# scenario: schema_probe_findings interprets empty_set_faulted
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets empty_set_faulted

from honest_test.persist_components import schema_probe_findings


def probe_schema_probe_findings_empty_set_faulted():
    findings = schema_probe_findings(table="widgets", outcome="empty_set_faulted")
    if not isinstance(findings, list) or len(findings) != 1:
        return [f"got {findings!r}, expected one Finding"]
    finding = findings[0]
    expected = {"kind": "failure", "code": "empty_set_faulted", "location": ""}
    actual = {field: finding.get(field) for field in expected}
    message = finding.get("message")
    if actual != expected:
        return [f"got {actual!r}, expected {expected!r}"]
    if not isinstance(message, str):
        return [f"got {message!r}, expected a message naming the table and contract"]
    normalized = message.casefold().replace("-", " ")
    if "widgets" not in normalized or not any(
        term in normalized for term in ('empty set', 'matching no rows', 'empty result')
    ):
        return [f"message {message!r} did not identify widgets and the empty set faulted contract"]
    return []


def run():
    failures = probe_schema_probe_findings_empty_set_faulted()
    for failure in failures:
        print(f"FAIL schema_probe_findings interprets empty_set_faulted: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
