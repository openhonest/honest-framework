# scenario: apply_suppression closes only the enabled rule in a mixed list
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression closes only the enabled rule in a mixed list

_SOURCE = b'# honest: disable HC-P004, HC-P005 HC-P011: legacy behavior\nfirst()\n# honest: enable HC-P004\nsecond()\n'
_FINDINGS = (('HC-P005', 2),
 ('HC-P004', 2),
 ('HC-P011', 4),
 ('HC-P011', 2),
 ('HC-P004', 4),
 ('HC-P005', 4))
_SEVERITIES = ('info', 'info', 'info', 'info', 'error', 'info')
_POLICY = ()


def probe_apply_suppression_closes_named_rule():
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
