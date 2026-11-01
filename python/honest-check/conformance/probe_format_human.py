"""format_human renders the human-readable default: the adoption line, one block per
diagnostic, and a 'Found N errors, M warnings.' tally.

A report with one error HC-P003 diagnostic renders text that carries 'Found ' and the
rule id. Returns text, performs no I/O.
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


# substrings the rendered human text must contain for a one-error report.
_WANT = ["Found ", "HC-P003"]


def probe_format_human():
    try:
        from honest_check import format_human
    except ImportError as exc:
        return [f"cannot import format_human: {exc}"]

    bad = []
    got = format_human(_report())
    if not isinstance(got, str):
        return [f"format_human(report) -> {got!r}, expected a string"]
    for want in _WANT:
        if want not in got:
            bad.append(f"format_human(report) is missing {want!r}; got {got!r}")
    return bad
