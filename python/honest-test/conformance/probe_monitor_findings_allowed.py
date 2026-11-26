# scenario: monitor_findings allows boundary links and empty records
# inherits: hd=python/honest-test/honest-test.hd::monitor_findings -> feature=specs/features/honest-test.feature::monitor_findings allows boundary links and empty records

from honest_type import link

from honest_test.honesty import monitor_findings


@link(boundary=True)
def _boundary(manifest):
    return manifest


@link(boundary=False)
def _watched(manifest):
    return manifest


def probe_monitor_findings_allowed():
    cases = (("allowed boundary", _boundary, ["builtins.open"]), ("empty record", _watched, []))
    failures = []
    for label, observed_link, record in cases:
        findings = monitor_findings(observed_link, record, "io")
        if findings != []:
            failures.append(f"{label}: got {findings!r}, expected no findings")
    return failures


def run():
    failures = probe_monitor_findings_allowed()
    for failure in failures:
        print(f"FAIL monitor_findings allows boundary links and empty records: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
