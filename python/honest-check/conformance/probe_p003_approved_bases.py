# scenario: _hc_p003 accepts the four approved direct Python bases
# inherits: hd=python/honest-check/honest-check.hd::_hc_p003 -> feature=specs/features/honest-check.feature::_hc_p003 accepts the four approved direct Python bases


def probe_p003_approved_bases():
    from honest_check import build_context
    from honest_check.rules import _hc_p003

    source = (
        b"class Record(TypedDict): pass\n"
        b"class Behavior(Protocol): pass\n"
        b"class Abstract(ABC): pass\n"
        b"class Problem(Exception): pass\n"
        b"class Custom(ABC, metaclass=ABCMeta, **options): pass\n"
    )
    actual = _hc_p003(build_context(source, "case.py", {}))
    return [] if not actual else [f"approved bases -> {actual!r}, expected no errors"]
