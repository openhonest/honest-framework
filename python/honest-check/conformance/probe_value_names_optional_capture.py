# scenario: _value_names reads an optional capture base name
# inherits: hd=python/honest-check/honest-check.hd::_value_names -> feature=specs/features/honest-check.feature::_value_names reads an optional capture base name


def probe_value_names_optional_capture():
    from honest_check import build_context
    from honest_check.bindings import _value_names

    canonical = b"from honest_type import maybe\n"
    alias = b"from honest_type import maybe as optional\n"
    cases = (
        ("literal", canonical, b'"Part"', {"Part"}),
        ("optional", canonical, b'maybe("Part")', {"Part"}),
        ("optional with comment", canonical, b'maybe(\n    # capture\n    "Part")', {"Part"}),
        ("renamed import", alias, b'optional("Part")', {"Part"}),
        ("optional dynamic", canonical, b"maybe(dynamic_name)", set()),
        ("unrelated qualifier", canonical, b'unrelated.maybe("Part")', set()),
        ("absent", canonical, None, set()),
    )
    failures = []
    for label, prelude, expression, expected in cases:
        source = prelude if expression is None else prelude + b"capture = " + expression
        ctx = build_context(source, "case.py", {})
        node = None if expression is None else ctx["root"].named_children[-1].named_children[0].child_by_field_name("right")
        actual = _value_names(ctx, node)
        if actual != expected:
            failures.append(f"{label} capture -> {actual!r}, expected {expected!r}")
    return failures
