# scenario: _matches checks inclusive ranges and excludes policy findings
# inherits: hd=python/honest-check/honest-check.hd::_matches -> feature=specs/features/honest-check.feature::_matches checks inclusive ranges and excludes policy findings


def probe_suppression_matches():
    from honest_check import build_context
    from honest_check.rules import _matches

    ctx = build_context(b"# honest: disable HC-P004, HC-SUP001, HC-SUP002: reason\n# honest: enable HC-P004\n", "case.py", {})
    comments = [node for node in ctx["nodes"] if node.type == "comment"]
    rules = {"HC-P004", "HC-SUP001", "HC-SUP002"}
    scoped = {
        "directive": {"line": 1, "node": comments[0], "verb": "disable", "rules": rules, "has_reason": True},
        "ranges": [{"rule": rule, "first_line": 2, "through_line": 4} for rule in sorted(rules)],
    }
    enable = {"directive": {"line": 2, "node": comments[1], "verb": "enable", "rules": {"HC-P004"}, "has_reason": False}, "ranges": []}
    cases = (
        ("start", scoped, "HC-P004", "case.py:2:1", True),
        ("end", scoped, "HC-P004", "case.py:4:1", True),
        ("before", scoped, "HC-P004", "case.py:1:1", False),
        ("after", scoped, "HC-P004", "case.py:5:1", False),
        ("other rule", scoped, "HC-P005", "case.py:3:1", False),
        ("no line", scoped, "HC-P004", "case.py", False),
        ("dead policy", scoped, "HC-SUP001", "case.py:3:1", False),
        ("reason policy", scoped, "HC-SUP002", "case.py:3:1", False),
        ("enable", enable, "HC-P004", "case.py:2:1", False),
    )
    failures = []
    for label, directive, rule, path, expected in cases:
        finding = {"rule_id": rule, "severity": "error", "message": "finding", "source_location": path, "context": "", "fixable": False}
        actual = _matches(directive, finding)
        if actual is not expected:
            failures.append(f"{label} match -> {actual!r}, expected {expected!r}")
    return failures
