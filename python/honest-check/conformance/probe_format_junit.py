"""format_junit renders JUnit XML: a <testsuites name="honest-check"> document.

A report with one error HC-P003 diagnostic renders text carrying '<testsuites'.
Returns text, no I/O.
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


def probe_format_junit():
    try:
        from honest_check import format_junit
    except ImportError as exc:
        return [f"cannot import format_junit: {exc}"]

    got = format_junit(_report())
    if not isinstance(got, str):
        return [f"format_junit(report) -> {got!r}, expected a string"]
    if "<testsuites" not in got:
        return [f"format_junit(report) is missing '<testsuites'; got {got!r}"]
    return []
