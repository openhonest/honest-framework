# scenario: _suppression_findings reports dead and missing reason findings in order
# inherits: hd=python/honest-check/honest-check.hd::_suppression_findings -> feature=specs/features/honest-check.feature::_suppression_findings reports dead and missing reason findings in order


def probe_suppression_suppression_findings():
    from honest_check import build_context
    from honest_check.rules import _suppression_findings

    source = (
        b"# honest: ignore HC-P004: reason\n"
        b"# honest: disable HC-P004:   \n"
        b"# honest: ignore HC-P004\n"
        b"# honest: enable HC-P004\n"
    )
    ctx = build_context(source, "case.py", {})
    comments = [node for node in ctx["nodes"] if node.type == "comment"]
    directives = [
        {
            "directive": {"line": line, "node": node, "verb": verb, "rules": {"HC-P004"}, "has_reason": line == 1},
            "ranges": [{"rule": "HC-P004", "first_line": line, "through_line": line}] if verb == "ignore" else [],
        }
        for line, (verb, node) in enumerate(zip(("ignore", "disable", "ignore", "enable"), comments), 1)
    ]
    raw = [
        {"rule_id": "HC-P004", "severity": "error", "message": "finding", "source_location": f"case.py:{line}:1", "context": "", "fixable": False}
        for line in (1, 3)
    ]
    actual = [
        (item["rule_id"], item["severity"], item["source_location"])
        for item in _suppression_findings(ctx, directives, raw)
    ]
    expected = [("HC-SUP001", "error", "case.py:2:1"), ("HC-SUP002", "error", "case.py:2:1"), ("HC-SUP002", "error", "case.py:3:1")]
    return [] if actual == expected else [f"suppression policy -> {actual!r}, expected {expected!r}"]
