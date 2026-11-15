"""Conformance probe for resolve_exit_code (honest-check).

Scenario (specs/features/honest-check.feature, Scenario: resolve_exit_code):
resolve_exit_code returns ExitCode '0' always when report.report_mode is true
(--report reports, it does not judge), otherwise '1' when report.errors is
greater than zero and '0' when no error survived; it never returns '2'.

A CheckReport is a record (honest-check.hd, type CheckReport) with the fields
below. resolve_exit_code reads report_mode and errors; every case states the
whole record so the input is explicit.
"""


def _report(errors, report_mode):
    return {
        "diagnostics": [],
        "errors": errors,
        "warnings": 0,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 58,
        "total_count": 58,
        "report_mode": report_mode,
    }


_CASES = [
    # Not a --report run, errors survived the downgrade: the gate fails with '1'.
    {"given": _report(errors=3, report_mode=False), "expect": "1"},
    # Not a --report run, no error survived: '0' (warnings and infos never block).
    {"given": _report(errors=0, report_mode=False), "expect": "0"},
    # A --report run overrides errors: '0' always, even with errors present.
    {"given": _report(errors=5, report_mode=True), "expect": "0"},
    # A --report run with no errors: still '0'.
    {"given": _report(errors=0, report_mode=True), "expect": "0"},
]


def probe_resolve_exit_code():
    """resolve_exit_code forces '0' under --report, else '1' on surviving errors and '0' otherwise."""
    try:
        from honest_check import resolve_exit_code
    except ImportError as exc:
        return [f"cannot import resolve_exit_code: {exc}"]

    bad = []
    for case in _CASES:
        got = resolve_exit_code(report=case["given"])
        if got != case["expect"]:
            bad.append(
                f"resolve_exit_code(errors={case['given']['errors']}, "
                f"report_mode={case['given']['report_mode']}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
