# scenario: schema_probe_findings interprets missing_required_field_rejected
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets missing_required_field_rejected

from honest_test.persist_components import schema_probe_findings


def probe_schema_probe_findings_missing_required_field_rejected():
    findings = schema_probe_findings(table="widgets", outcome="missing_required_field_rejected")
    if findings != []:
        return [f"got {findings!r}, expected no findings"]
    return []


def run():
    failures = probe_schema_probe_findings_missing_required_field_rejected()
    for failure in failures:
        print(f"FAIL schema_probe_findings interprets missing_required_field_rejected: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
