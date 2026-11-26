# scenario: pure_call_findings reports ordered errors at the caller declaration path
# inherits: hd=python/honest-check/honest-check.hd::pure_call_findings -> feature=specs/features/honest-check.feature::pure_call_findings reports ordered errors at the caller declaration path
"""Report failed pure calls in authored order at the declaring file."""

_PATH = "consumer.hd"
_CALLS = [{'caller': 'load',
  'target': 'world.read',
  'module': 'world',
  'status': 'invalid_role'},
 {'caller': 'load',
  'target': 'utils.answer',
  'module': 'utils',
  'status': 'resolved'},
 {'caller': 'build',
  'target': 'absent.answer',
  'module': 'absent',
  'status': 'unresolved'}]
_REASONS = {
    "invalid_role": ("plain function", "side effects", "boundaryless module"),
    "unresolved": ("resolve", "declared function"),
}
_EXPECTED = [
    ("HC-REF007", "error", _PATH, True, True, True),
    ("HC-REF006", "error", _PATH, True, True, True),
]


def probe_pure_call_findings_ordered():
    """Check diagnostic order, path, severity, authored names and distinct repair reasons."""
    try:
        from honest_check.seams import pure_call_findings
    except ImportError as exc:
        return [f"cannot import pure_call_findings: {exc}"]

    findings = pure_call_findings(_CALLS, _PATH)
    if len(findings) != len(_EXPECTED):
        return [f"pure_call_findings returned {findings!r}, expected two diagnostics"]
    failed_calls = [call for call in _CALLS if call["status"] != "resolved"]
    got = [
        (
            finding["rule_id"],
            finding["severity"],
            finding["source_location"],
            call["caller"] in finding["message"],
            call["target"] in finding["message"],
            all(term in finding["message"] for term in _REASONS[call["status"]]),
        )
        for finding, call in zip(findings, failed_calls, strict=True)
    ]
    if got != _EXPECTED:
        return [f"pure_call_findings returned {findings!r}, expected the ordered names and reasons {_REASONS!r}"]
    return []
