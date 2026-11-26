# scenario: apply_suppression reports redundant disables and blank reasons
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression reports redundant disables and blank reasons

_SOURCE = b'# honest: disable HC-P004: legacy I/O\n# honest: disable HC-P004:    \nrun()\n'
_FINDINGS = (('HC-P004', 3),)
_SEVERITIES = ('info',)
_POLICY = (('HC-SUP001', 'error', 2), ('HC-SUP002', 'error', 2))


def probe_apply_suppression_reports_redundancy():
    from honest_check import apply_suppression, build_context

    ctx = build_context(_SOURCE, "case.py", {})
    findings = [
        {
            "rule_id": rule,
            "severity": "error",
            "message": f"Finding {rule} on line {line}",
            "source_location": f"case.py:{line}:1",
            "context": f"Context from line {line}",
            "fixable": rule == "HC-P005",
        }
        for rule, line in _FINDINGS
    ]
    expected = [
        {**finding, "severity": severity}
        for finding, severity in zip(findings, _SEVERITIES)
    ]
    actual = apply_suppression(ctx, findings)
    actual_raw = actual[:len(findings)]
    actual_policy = tuple(
        (finding["rule_id"], finding["severity"], int(finding["source_location"].rsplit(":", 2)[1]))
        for finding in actual[len(findings):]
    )

    failures = []
    if actual_raw != expected:
        observed = [(finding["rule_id"], finding["severity"], finding["source_location"]) for finding in actual_raw]
        failures.append(f"raw findings differ in fields, order or severity: {observed!r}")
    if actual_policy != _POLICY:
        failures.append(f"policy findings -> {actual_policy!r}, expected {_POLICY!r}")
    return failures
