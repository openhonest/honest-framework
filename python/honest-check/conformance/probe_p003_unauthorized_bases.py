# scenario: _hc_p003 reports each disallowed direct Python base in source order
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 reports each disallowed direct Python base in source order


def probe_p003_unauthorized_bases():
    import re
    from honest_check import build_context
    from honest_check.rules import _hc_p003

    source = (
        b"class Mixed(TypedDict, NamedTuple, Enum): pass\n"
        b"class MetaclassAsBase(ABCMeta, Exception): pass\n"
    )
    findings = _hc_p003(build_context(source, "case.py", {}))
    actual = [
        (finding["rule_id"], finding["severity"], finding["source_location"],
         re.findall(r"\b(?:NamedTuple|Enum|ABCMeta)\b", finding["message"]))
        for finding in findings
    ]
    expected = [
        ("HC-P003", "error", "case.py:1:1", ["NamedTuple"]),
        ("HC-P003", "error", "case.py:1:1", ["Enum"]),
        ("HC-P003", "error", "case.py:2:1", ["ABCMeta"]),
    ]
    return [] if actual == expected else [f"unauthorized bases -> {actual!r}, expected {expected!r}"]
