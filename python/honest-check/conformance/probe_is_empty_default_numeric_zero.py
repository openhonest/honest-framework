# scenario: is_empty_default accepts zero spellings and rejects nonzero defaults
# inherits: hd=python/honest-check/honest-check.hd::is_empty_default -> feature=specs/features/honest-check.feature::is_empty_default accepts zero spellings and rejects nonzero defaults

_CASES = (
    ('0x0', True),
    ('0O_0', True),
    ('0B_0', True),
    ('0_0', True),
    ('0.0', True),
    ('0e3', True),
    ('0j', True),
    ('(-0)', True),
    ('(+0.0)', True),
    ('-0', True),
    ('+0.0', True),
    ('0x2', False),
    ('-1.5', False),
    ('1j', False),
)


def probe_is_empty_default_numeric_zero():
    from honest_check import build_context, is_empty_default

    failures = []
    for expression, expected in _CASES:
        try:
            source = f"def check(value={expression}): pass".encode()
            ctx = build_context(source, "case.py", {})
            param = next(node for node in ctx["nodes"] if node.type == "default_parameter")
            actual = is_empty_default(ctx, param.child_by_field_name("value"))
        except (ValueError, TypeError) as error:
            failures.append(f"{expression!r}: raised {type(error).__name__}: {error}")
            continue
        if actual is not expected:
            failures.append(f"{expression!r}: returned {actual!r}, expected {expected!r}")
    return failures
