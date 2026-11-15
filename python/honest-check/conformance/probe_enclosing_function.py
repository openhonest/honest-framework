"""Honest probe for honest-check's enclosing_function (Scenario: enclosing_function).

enclosing_function returns the nearest enclosing function_definition of a node,
climbing parents, or NOTHING (None) at module scope.

Cases parse real Python with honest-parse and hand the real node to the function:
an assignment inside a single `def f` (returns f), an assignment at module scope
(returns None, the explicit absence), and an assignment inside a nested `def inner`
(returns inner, not the outer function). The nested case is what pins "nearest":
a stub that returns the first/outermost function fails it, and a stub that always
returns None fails the two non-absence cases.
"""

from honest_parse import parse, walk


def _find(root, ntype, text):
    for n in walk(root):
        if n.type == ntype and n.text.decode() == text:
            return n
    return None


# Each case: a real source, the (type, text) of the node handed in, and the
# text prefix the returned enclosing function_definition must carry — or None
# for the module-scope absence case.
_CASES = [
    {
        "source": "def f():\n    x = 1\n",
        "target": ("assignment", "x = 1"),
        "expect_fn_prefix": "def f",
    },
    {
        # Module scope: no enclosing function, so the explicit absence None.
        "source": "x = 1\n",
        "target": ("assignment", "x = 1"),
        "expect_fn_prefix": None,
    },
    {
        # Nested: the nearest enclosing function is inner, never outer.
        "source": "def outer():\n    def inner():\n        y = 2\n",
        "target": ("assignment", "y = 2"),
        "expect_fn_prefix": "def inner",
    },
]


def probe_enclosing_function():
    """enclosing_function climbs to the nearest function_definition, or None at module scope."""
    try:
        from honest_check import enclosing_function
    except ImportError as exc:
        return [f"cannot import enclosing_function: {exc}"]

    bad = []
    for case in _CASES:
        root = parse(case["source"].encode("utf-8"), "python").root_node
        ntype, ntext = case["target"]
        node = _find(root, ntype, ntext)
        if node is None:
            bad.append(f"test setup: no {ntype} {ntext!r} in {case['source']!r}")
            continue
        got = enclosing_function(node)
        prefix = case["expect_fn_prefix"]
        if prefix is None:
            if got is not None:
                bad.append(
                    f"enclosing_function(<{ntype} {ntext!r}> at module scope) -> "
                    f"{got!r}, expected None"
                )
            continue
        if got is None or got.type != "function_definition" or not got.text.decode().startswith(prefix):
            got_repr = None if got is None else f"<{got.type} {got.text.decode()!r}>"
            bad.append(
                f"enclosing_function(<{ntype} {ntext!r}>) -> {got_repr}, "
                f"expected a function_definition starting {prefix!r}"
            )
    return bad
