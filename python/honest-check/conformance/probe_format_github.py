"""Honest probe for honest-check's format_github (feature Scenario: format_github).

format_github renders GitHub Actions workflow-command annotations from a prepared
CheckReport: one '::error' line for an error-severity finding and '::warning' otherwise,
each carrying file, line and col from source_location, title=<rule id>, with the message as
the body. It returns the annotation text and does no I/O.

Each case pins the fixed fragments of one annotation: the severity-driven command prefix,
the source_location fields in GitHub's file=/line=/col= form, the title=<rule id>, and the
message. A stub returning "" fails the '::error'/'::warning' checks. The error case and the
warning case together prove the severity drives the command word.
"""


def _diag(rule_id, severity, message, source_location):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": source_location,
        "context": "",
        "fixable": False,
    }


def _report(diagnostics, errors, warnings):
    return {
        "diagnostics": diagnostics,
        "errors": errors,
        "warnings": warnings,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 58,
        "total_count": 58,
        "report_mode": False,
    }


# Each case: the report to render, and the fixed fragments the annotation must carry.
_CASES = [
    {
        "report": _report(
            [_diag("HC-P001", "error", "msg one", "src/x.py:10:5")],
            errors=1, warnings=0,
        ),
        "contains": ["::error", "file=src/x.py", "line=10", "col=5", "title=HC-P001", "msg one"],
    },
    {
        "report": _report(
            [_diag("HC-P004", "warning", "msg two", "src/y.py:3:1")],
            errors=0, warnings=1,
        ),
        "contains": ["::warning", "file=src/y.py", "line=3", "col=1", "title=HC-P004", "msg two"],
    },
]


def probe_format_github():
    """format_github renders ::error/::warning annotations carrying file, line, col and title."""
    try:
        from honest_check import format_github
    except ImportError as exc:
        return [f"cannot import format_github: {exc}"]

    bad = []
    for case in _CASES:
        try:
            got = format_github(report=case["report"])
        except Exception as exc:
            bad.append(f"format_github raised {exc!r}")
            continue
        for fragment in case["contains"]:
            if fragment not in got:
                bad.append(f"format_github output missing {fragment!r}; got {got!r}")
    return bad
