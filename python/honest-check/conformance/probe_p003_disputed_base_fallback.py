# scenario: _hc_p003 preserves class-level fallback for disputed and unresolved Python bases
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 preserves class-level fallback for disputed and unresolved Python bases


def probe_p003_disputed_base_fallback():
    from honest_check import build_context
    from honest_check.rules import _hc_p003

    source = (
        b"class Disputed(BaseException): pass\n"
        b"class Unresolved(typing.Protocol): pass\n"
        b"class ApprovedDisputed(Protocol, BaseException): pass\n"
        b"class ApprovedUnresolved(Protocol, typing.Protocol): pass\n"
    )
    findings = _hc_p003(build_context(source, "case.py", {}))
    observed = [
        (finding["rule_id"], finding["severity"], finding["source_location"])
        for finding in findings
    ]
    expected = [("HC-P003", "error", "case.py:1:1"), ("HC-P003", "error", "case.py:2:1")]
    return [] if observed == expected else [f"fallback diagnostic locations -> {observed!r}, expected {expected!r}"]
