# scenario: _hc_p003 reports implicit object inheritance when no actual Python base is declared
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 reports implicit object inheritance when no actual Python base is declared


def probe_p003_implicit_bases():
    import re
    from honest_check import build_context
    from honest_check.rules import _hc_p003

    source = (
        b"class Bare: pass\n"
        b"class Empty(): pass\n"
        b"class MetaclassOnly(metaclass=ABCMeta): pass\n"
        b"class KeywordsOnly(**options): pass\n"
    )
    findings = _hc_p003(build_context(source, "case.py", {}))
    actual = [
        (finding["rule_id"], finding["severity"], finding["source_location"], bool(re.search(
            r"implicit object|(?:no|without) (?:actual |declared |explicit )*bases?",
            finding["message"], re.IGNORECASE,
        )))
        for finding in findings
    ]
    expected = [("HC-P003", "error", f"case.py:{line}:1", True) for line in (1, 2, 3, 4)]
    return [] if actual == expected else [f"implicit bases -> {actual!r}, expected {expected!r}"]
