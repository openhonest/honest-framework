"""format_github renders GitHub Actions workflow-command annotations: one '::error'
or '::warning' line per finding.

A report with one error HC-P003 diagnostic renders text carrying a line that starts
with '::error file='. Returns text, no I/O.
"""


def _report():
    return {
        "diagnostics": [
            {
                "rule_id": "HC-P003",
                "severity": "error",
                "message": "class declaration",
                "source_location": "src/x.py:10:1",
                "context": "class X:",
                "fixable": False,
            }
        ],
        "errors": 1,
        "warnings": 0,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 50,
        "total_count": 50,
        "report_mode": False,
    }


def probe_format_github():
    try:
        from honest_check import format_github
    except ImportError as exc:
        return [f"cannot import format_github: {exc}"]

    got = format_github(_report())
    if not isinstance(got, str):
        return [f"format_github(report) -> {got!r}, expected a string"]
    if not any(line.startswith("::error file=") for line in got.splitlines()):
        return [
            f"format_github(report) has no line starting '::error file='; got {got!r}"
        ]
    return []
