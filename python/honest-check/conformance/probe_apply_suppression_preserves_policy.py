# scenario: apply_suppression ignores unrecognized verbs and preserves policy findings
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression ignores unrecognized verbs and preserves policy findings

_SOURCE = b'# honest: reverb HC-P004: unrecognized verb\n# honest: ignore HC-SUP001, HC-SUP002: attempted suppression\n'
_FINDINGS = (('HC-P004', 1), ('HC-SUP002', 2), ('HC-SUP001', 2))
_SEVERITIES = ('error', 'error', 'error')
_POLICY = (('HC-SUP001', 'error', 2),)


def probe_apply_suppression_preserves_policy():
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
