# scenario: schema_probe_findings interprets empty_rows
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets empty_rows

from honest_test.persist_components import schema_probe_findings


def probe_schema_probe_findings_empty_rows():
    findings = schema_probe_findings(table="widgets", outcome="empty_rows")
    if findings != []:
        return [f"got {findings!r}, expected no findings"]
    return []


def run():
    failures = probe_schema_probe_findings_empty_rows()
    for failure in failures:
        print(f"FAIL schema_probe_findings interprets empty_rows: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
