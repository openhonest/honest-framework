# scenario: monitor_findings reports watched calls from a non-boundary link
# inherits: hd=python/honest-test/honest-test.hd::monitor_findings -> feature=specs/features/honest-test.feature::monitor_findings reports watched calls from a non-boundary link

from honest_type import link

from honest_test.honesty import monitor_findings


@link(boundary=False)
def _watched(manifest):
    return manifest


def probe_monitor_findings_warning():
    cases = (
        ("nondeterminism", ["random.random"], "nondeterminism_detected"),
        ("io", ["builtins.open"], "io_detected"),
        ("other", ["builtins.print"], "io_detected"),
    )
    failures = []
    for kind, record, code in cases:
        findings = monitor_findings(_watched, record, kind)
        actual = [(finding["kind"], finding["code"]) for finding in findings]
        if actual != [("warning", code)]:
            failures.append(f"{kind}: got {actual!r}, expected one {code} warning")
        elif record[0] not in findings[0]["message"]:
            failures.append(f"{kind}: warning omitted the recorded call {record[0]!r}")
    return failures


def run():
    failures = probe_monitor_findings_warning()
    for failure in failures:
        print(f"FAIL monitor_findings reports watched calls from a non-boundary link: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
