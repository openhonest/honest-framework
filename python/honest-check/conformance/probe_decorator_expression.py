"""Honest probe for honest-check's decorator_expression (Scenario: decorator_expression).

decorator_expression returns the expression a decorator applies — the identifier,
attribute or call after the `@`, which a parsed decorator carries as its first
named child. The cases parse real Python with honest-parse, hand the real
decorator node to decorator_expression, and pin the grammar type and source text
of the expression node it must return for a bare name, a dotted-and-called
decorator, and a dotted (uncalled) decorator.
"""

# Each case: a real one-decorator source and the (type, text) of the expression
# node decorator_expression must return from that decorator.
_CASES = [
    {
        "source": "@boundary\ndef f():\n    pass\n",
        "type": "identifier",
        "text": "boundary",
    },
    {
        "source": "@functools.lru_cache(maxsize=1)\ndef f():\n    pass\n",
        "type": "call",
        "text": "functools.lru_cache(maxsize=1)",
    },
    {
        "source": "@app.route('/x')\ndef f():\n    pass\n",
        "type": "call",
        "text": "app.route('/x')",
    },
]


def probe_decorator_expression():
    """decorator_expression returns a decorator's first named child — its applied expression."""
    try:
        from honest_check import decorator_expression
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import decorator_expression: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "python")
        root = tree.root_node
        decorator = None
        for node in walk(root):
            if node.type == "decorator":
                decorator = node
                break
        if decorator is None:
            bad.append(f"test setup: no decorator node in {case['source']!r}")
            continue
        got = decorator_expression(decorator)
        got_type = getattr(got, "type", None)
        got_text = got.text.decode("utf-8") if hasattr(got, "text") else got
        if (got_type, got_text) != (case["type"], case["text"]):
            bad.append(
                f"decorator_expression({case['source']!r}) -> "
                f"({got_type!r}, {got_text!r}), expected ({case['type']!r}, {case['text']!r})"
            )
    return bad
