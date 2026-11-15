"""Honest probe for honest-check's decorators_of (feature Scenario: decorators_of).

decorators_of returns the decorator nodes applied to a function — the decorator
children of the enclosing decorated_definition — or the empty list for an
undecorated function. The cases parse real Python with honest-parse, hand the
real function_definition node (plus a real CheckContext) to decorators_of, and
pin the decorator texts it must return, including the explicit empty-list case
for a function carrying no decorator.
"""

# Each case: a real source, the function whose decorators_of is read, and the
# decorator texts (the `@...` spans) decorators_of must return in source order.
_CASES = [
    {
        "source": "@boundary\n@functools.lru_cache(maxsize=1)\ndef f():\n    pass\n",
        "func": "f",
        "expect": ["@boundary", "@functools.lru_cache(maxsize=1)"],
    },
    {
        # Absence: an undecorated function has no enclosing decorated_definition,
        # so decorators_of returns the empty list, written out.
        "source": "def g():\n    pass\n",
        "func": "g",
        "expect": [],
    },
]


def probe_decorators_of():
    """decorators_of returns a function's decorator nodes, or the empty list when it has none."""
    try:
        from honest_check import decorators_of
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import decorators_of: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "python")
        root = tree.root_node
        ctx = {
            "root": root,
            "nodes": walk(root),
            "aliases": {},
            "roles": {},
            "source": root.text,
            "path": "case.py",
            "rule_config": {},
        }
        fdef = None
        for node in walk(root):
            if node.type == "function_definition" and node.named_children and \
                    node.named_children[0].text.decode("utf-8") == case["func"]:
                fdef = node
                break
        if fdef is None:
            bad.append(f"test setup: no function_definition named {case['func']!r}")
            continue
        got = decorators_of(ctx, fdef)
        got_texts = [n.text.decode("utf-8") for n in got] if isinstance(got, list) else got
        if got_texts != case["expect"]:
            bad.append(
                f"decorators_of(<{case['func']}>) -> {got_texts!r}, expected {case['expect']!r}"
            )
    return bad
