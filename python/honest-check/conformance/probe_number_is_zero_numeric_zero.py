# scenario: _number_is_zero recognizes zero by literal value and syntax
# inherits: hd=python/honest-check/honest-check.hd::_number_is_zero -> feature=specs/features/honest-check.feature::_number_is_zero recognizes zero by literal value and syntax

_CASES = (
    ('0', True),
    ('0_0', True),
    ('0x0', True),
    ('0O_0', True),
    ('0B_0', True),
    ('0.0', True),
    ('0e3', True),
    ('0J', True),
    ('(-0x0)', True),
    ('((+0.0))', True),
    ('(\n    # numeric comment\n    0\n)', True),
    ('0x1', False),
    ('0o7', False),
    ('0b10', False),
    ('1e-3', False),
    ('1j', False),
    ('-(1)', False),
    ('(+0.5)', False),
    ('~0', False),
    ('0 + 0', False),
    ('zero', False),
    ('make_zero()', False),
)


def probe_number_is_zero_numeric_zero():
    from honest_check.analysis import _number_is_zero
    from honest_parse import parse

    failures = []
    for expression, expected in _CASES:
        try:
            tree = parse(expression.encode(), "python")
            node = tree.root_node.named_children[0].named_children[0]
            actual = _number_is_zero(node)
        except (ValueError, TypeError) as error:
            failures.append(f"{expression!r}: raised {type(error).__name__}: {error}")
            continue
        if actual is not expected:
            failures.append(f"{expression!r}: returned {actual!r}, expected {expected!r}")
    return failures
