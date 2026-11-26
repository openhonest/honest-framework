# scenario: _resolve_one preserves findings while downgrading matching severity
# inherits: hd=python/honest-check/honest-check.hd::_resolve_one -> feature=specs/features/honest-check.feature::_resolve_one preserves findings while downgrading matching severity


def probe_suppression_resolve_one():
    from honest_check import build_context
    from honest_check.rules import _resolve_one

    ctx = build_context(b"# honest: ignore HC-P004: fixture\n", "case.py", {})
    comment = next(node for node in ctx["nodes"] if node.type == "comment")
    scoped = {"directive": {"line": 1, "node": comment, "verb": "ignore", "rules": {"HC-P004"}, "has_reason": True}, "ranges": [{"rule": "HC-P004", "first_line": 1, "through_line": 1}]}
    finding = {"rule_id": "HC-P004", "severity": "error", "message": "Keep this message", "source_location": "case.py:1:5", "context": "Keep this context", "fixable": True}
    matched = _resolve_one(finding, [scoped])
    unmatched = _resolve_one(finding, [])
    expected = {**finding, "severity": "info"}
    failures = []
    if matched != expected or matched is finding or finding["severity"] != "error":
        failures.append(f"matched finding -> {matched!r}, expected an independent copy {expected!r}")
    if unmatched is not finding or unmatched["severity"] != "error":
        failures.append(f"unmatched finding -> {unmatched!r}, expected original error finding")
    return failures
