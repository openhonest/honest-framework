# scenario: _directive_record extracts recognized rules and reason presence
# inherits: hd=python/honest-check/honest-check.hd::_directive_record -> feature=specs/features/honest-check.feature::_directive_record extracts recognized rules and reason presence


def probe_suppression_directive_record():
    from honest_check import build_context
    from honest_check.rules import _directive_record

    cases = (
        ("mixed", "# honest: disable HC-P004, HC-P005 HC-P011: a reason: with a colon", "disable", {"HC-P004", "HC-P005", "HC-P011"}, True),
        ("whitespace separated", "# honest: disable HC-P004 HC-P005: reason", "disable", {"HC-P004", "HC-P005"}, True),
        ("comma without space", "# honest: disable HC-P004,HC-P005: reason", "disable", {"HC-P004", "HC-P005"}, True),
        ("blank", "# honest: ignore HC-P004:  ", "ignore", {"HC-P004"}, False),
        ("verb", "# honest: reverb HC-P004: reason", None, set(), False),
        ("empty", "# honest: ignore : reason", None, set(), False),
    )
    failures = []
    for label, text, verb, rules, reason in cases:
        ctx = build_context(f"before = 0\n{text}\n".encode(), "case.py", {})
        node = next(member for member in ctx["nodes"] if member.type == "comment")
        actual = _directive_record(node)
        expected = None if verb is None else {"line": 2, "node": node, "verb": verb, "rules": rules, "has_reason": reason}
        if actual != expected:
            failures.append(f"{label} directive -> {actual!r}, expected {expected!r}")
    return failures
