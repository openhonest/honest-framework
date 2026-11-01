"""format_json renders the JSON machine format: an object with a 'summary' and a
diagnostics array whose entries carry 'rule'.

A report with one error HC-P003 diagnostic renders text that parses as JSON, carries
a 'summary', and whose first diagnostic's 'rule' is 'HC-P003'. Returns text, no I/O.
"""

import json


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


def probe_format_json():
    try:
        from honest_check import format_json
    except ImportError as exc:
        return [f"cannot import format_json: {exc}"]

    bad = []
    got = format_json(_report())
    if not isinstance(got, str):
        return [f"format_json(report) -> {got!r}, expected a string"]
    try:
        obj = json.loads(got)
    except (ValueError, TypeError) as exc:
        return [f"format_json(report) is not valid JSON: {exc}; got {got!r}"]
    if "summary" not in obj:
        bad.append(f"format_json(report) has no 'summary' key; got keys {list(obj)}")
    diags = obj.get("diagnostics")
    if not diags:
        bad.append(f"format_json(report) 'diagnostics' is empty or absent; got {obj!r}")
    elif diags[0].get("rule") != "HC-P003":
        bad.append(
            f"format_json(report) diagnostics[0]['rule'] -> {diags[0].get('rule')!r}, "
            f"expected 'HC-P003'"
        )
    return bad
