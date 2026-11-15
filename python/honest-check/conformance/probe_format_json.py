"""Honest probe for honest-check's format_json (feature Scenario: format_json).

format_json renders the machine JSON from a prepared CheckReport: an object with version,
timestamp, a summary carrying errors/warnings/infos/adoption/enforced_rules, and a
diagnostics array whose entries split source_location into file/line/col and carry rule,
severity, message, context and fixable. It returns the JSON text and does no I/O.

The probe parses the text back and asserts the structure, rather than pinning whitespace.
The summary counts and the per-diagnostic fields are the non-trivial literals the scenario
fixes; a stub returning "" fails to parse and a stub returning "{}" misses every key. The
line/col field type (int or str) is not fixed by the scenario, so the probe compares them
through int().
"""
import json


def _diag(rule_id, severity, message, source_location, context, fixable):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": source_location,
        "context": context,
        "fixable": fixable,
    }


_REPORT = {
    "diagnostics": [
        _diag("HC-P001", "error", "msg one", "src/x.py:10:5", "if a:", False),
    ],
    "errors": 2,
    "warnings": 1,
    "infos": 0,
    "rule_counts": {},
    "adoption": "Boundary",
    "enforced_count": 17,
    "total_count": 58,
    "report_mode": False,
}


def probe_format_json():
    """format_json renders a JSON object with the summary counts and the split diagnostics."""
    try:
        from honest_check import format_json
    except ImportError as exc:
        return [f"cannot import format_json: {exc}"]

    bad = []
    try:
        text = format_json(report=_REPORT)
    except Exception as exc:
        return [f"format_json raised {exc!r}"]

    try:
        obj = json.loads(text)
    except Exception as exc:
        return [f"format_json output did not parse as JSON ({exc!r}); got {text!r}"]

    for key in ("version", "timestamp", "summary", "diagnostics"):
        if key not in obj:
            bad.append(f"format_json object missing top-level key {key!r}")

    summary = obj.get("summary", {})
    for field, want in (("errors", 2), ("warnings", 1), ("infos", 0), ("adoption", "Boundary")):
        if summary.get(field) != want:
            bad.append(f"format_json summary.{field} -> {summary.get(field)!r}, expected {want!r}")
    if "enforced_rules" not in summary:
        bad.append("format_json summary missing 'enforced_rules'")

    diags = obj.get("diagnostics", [])
    if not isinstance(diags, list) or len(diags) != 1:
        bad.append(f"format_json diagnostics -> {diags!r}, expected a one-entry list")
        return bad

    entry = diags[0]
    for field, want in (
        ("file", "src/x.py"),
        ("rule", "HC-P001"),
        ("severity", "error"),
        ("message", "msg one"),
        ("context", "if a:"),
        ("fixable", False),
    ):
        if entry.get(field) != want:
            bad.append(f"format_json diagnostic.{field} -> {entry.get(field)!r}, expected {want!r}")
    for field, want in (("line", 10), ("col", 5)):
        try:
            have = int(entry.get(field))
        except (TypeError, ValueError):
            have = None
        if have != want:
            bad.append(f"format_json diagnostic.{field} -> {entry.get(field)!r}, expected {want}")
    return bad
