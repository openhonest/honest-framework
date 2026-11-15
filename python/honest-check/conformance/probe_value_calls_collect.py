"""Honest probe for honest-check's value_calls_collect (Scenario: value_calls_collect).

value_calls_collect is true when a bound value calls one of the resolved `collect`
names anywhere inside it (HC-ST002, a JavaScript shadow-of-user-state rule). Each
case parses a real JavaScript binding with honest-parse and hands the real value
expression (the right side of `const x = <value>;`) and the resolved collect names.

A direct call and a nested call both pin true ("anywhere inside it"); a call to a
different name pins false; a literal with no call is the boundary false. A
`return False` stub fails the two true cases; a `return True` stub fails the two
false cases.
"""

# Each case: a real JS binding source, the resolved collect names, and whether the
# bound value calls one of them anywhere inside.
_CASES = [
    {"source": "const x = collect(el);", "collect_names": {"collect"}, "expect": True},
    # Anywhere inside: the collect call is nested within another call.
    {"source": "const x = foo(collect(el));", "collect_names": {"collect"}, "expect": True},
    {"source": "const x = foo(el);", "collect_names": {"collect"}, "expect": False},
    # Boundary: a literal value calls nothing.
    {"source": "const x = 42;", "collect_names": {"collect"}, "expect": False},
]


def probe_value_calls_collect():
    """value_calls_collect is true when a bound value calls a resolved collect name anywhere inside it."""
    try:
        from honest_check import value_calls_collect
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import value_calls_collect: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "javascript")
        declarator = next(
            (n for n in walk(tree.root_node) if n.type == "variable_declarator"), None
        )
        if declarator is None or not declarator.named_children:
            bad.append(f"test setup: no variable_declarator in {case['source']!r}")
            continue
        value_node = declarator.named_children[-1]
        got = value_calls_collect(value_node, case["collect_names"])
        if got != case["expect"]:
            bad.append(
                f"value_calls_collect({case['source']!r}, {case['collect_names']}) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
