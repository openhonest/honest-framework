"""format_json renders the JSON machine format: a document with a version, a timestamp,
a summary, a diagnostics array and the rule counts.

Every field is pinned by value. The summary echoes the report's counts, adoption and
enforced-rule total under their own keys; each diagnostic carries its rule, severity,
split file/line/col, message, context and fixable flag under their own keys. The
document is serialized with a two-space indent, so the top-level keys sit two spaces in.
A three-colon location splits from the right into file, line and col.
"""

import json


def _diag(source_location, rule_id="HC-P003"):
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": "class declaration",
        "source_location": source_location,
        "context": "class X:",
        "fixable": False,
    }


def _report(diag):
    return {
        "diagnostics": [diag],
        "errors": 1,
        "warnings": 0,
        "infos": 0,
        "rule_counts": {"HC-P003": 1},
        "adoption": "Declared",
        "enforced_count": 50,
        "total_count": 50,
        "report_mode": False,
    }


def probe_format_json():
    try:
        from honest_check import format_json
        from honest_check.report import by_format
    except ImportError as exc:
        return [f"cannot import format_json: {exc}"]

    bad = []
    got = format_json(_report(_diag("src/x.py:10:1")))
    if not isinstance(got, str):
        return [f"format_json(report) -> {got!r}, expected a string"]

    # The two-space indent puts the top-level keys exactly two spaces in; a wider or
    # narrower indent moves them, even though the parsed object is unchanged.
    if '\n  "version": "0.1"' not in got:
        bad.append(f"format_json did not serialize with a two-space indent; got {got!r}")

    try:
        obj = json.loads(got)
    except (ValueError, TypeError) as exc:
        return bad + [f"format_json(report) is not valid JSON: {exc}; got {got!r}"]

    if obj.get("version") != "0.1":
        bad.append(f"format_json version -> {obj.get('version')!r}, expected '0.1'")
    if "timestamp" not in obj:
        bad.append(f"format_json has no 'timestamp' key; got keys {sorted(obj)}")

    want_summary = {
        "errors": 1,
        "warnings": 0,
        "infos": 0,
        "adoption": "Declared",
        "enforced_rules": 50,
    }
    if obj.get("summary") != want_summary:
        bad.append(f"format_json summary -> {obj.get('summary')!r}, expected {want_summary}")

    if obj.get("rule_counts") != {"HC-P003": 1}:
        bad.append(
            f"format_json rule_counts -> {obj.get('rule_counts')!r}, expected {{'HC-P003': 1}}"
        )

    diags = obj.get("diagnostics")
    want_diag = {
        "rule": "HC-P003",
        "severity": "error",
        "file": "src/x.py",
        "line": "10",
        "col": "1",
        "message": "class declaration",
        "context": "class X:",
        "fixable": False,
    }
    if not diags:
        bad.append(f"format_json 'diagnostics' is empty or absent; got {obj!r}")
    elif diags[0] != want_diag:
        bad.append(f"format_json diagnostics[0] -> {diags[0]!r}, expected {want_diag}")

    # A three-colon location splits from the right: file 'w:x', line 'y', col 'z'.
    got3 = format_json(_report(_diag("w:x:y:z")))
    obj3 = json.loads(got3)
    diag3 = obj3["diagnostics"][0]
    if (diag3.get("file"), diag3.get("line"), diag3.get("col")) != ("w:x", "y", "z"):
        bad.append(
            f"format_json widened the right-split of a three-colon location; "
            f"file/line/col were {(diag3.get('file'), diag3.get('line'), diag3.get('col'))}"
        )

    # The format dispatch binds the json word to this renderer.
    if by_format.get("json") is not format_json:
        bad.append(
            f"by_format['json'] -> {by_format.get('json')!r}, expected format_json"
        )

    return bad
