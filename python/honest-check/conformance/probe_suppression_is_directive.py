# scenario: _is_directive recognizes the stripped honest prefix
# inherits: hd=python/honest-check/honest-check.hd::_is_directive -> feature=specs/features/honest-check.feature::_is_directive recognizes the stripped honest prefix


def probe_suppression_is_directive():
    from honest_check.rules import _is_directive

    cases = (
        ("  honest: ignore HC-P004", True), ("honest:", True),
        ("note: honest: ignore HC-P004", False), ("just a comment", False),
    )
    return [
        f"prefix {text!r} -> {actual!r}, expected {expected!r}"
        for text, expected in cases if (actual := _is_directive(text)) is not expected
    ]
