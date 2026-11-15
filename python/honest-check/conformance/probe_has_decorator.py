"""Honest probe for honest-check's has_decorator (Scenario: has_decorator).

has_decorator returns true when a function carries a decorator whose target is
`name`, bare or called. The cases parse real Python with honest-parse, build a
real CheckContext, hand the real function_definition node and a name to the
function, and pin true for a bare match, a called match and a dotted-and-called
match whose final name is `name`, and false for a non-matching decorator and for
an undecorated function.
"""

# Each case: a real source, the function read, the decorator name looked for, and
# whether has_decorator must find it.
_CASES = [
    {"source": "@link\ndef f():\n    pass\n", "func": "f", "name": "link", "expect": True},
    {"source": "@link(x=1)\ndef f():\n    pass\n", "func": "f", "name": "link", "expect": True},
    {
        "source": "@functools.lru_cache(maxsize=1)\ndef f():\n    pass\n",
        "func": "f",
        "name": "lru_cache",
        "expect": True,
    },
    {"source": "@orchestrator\ndef f():\n    pass\n", "func": "f", "name": "link", "expect": False},
    # Absence: an undecorated function carries no decorator named link.
    {"source": "def f():\n    pass\n", "func": "f", "name": "link", "expect": False},
]


def probe_has_decorator():
    """has_decorator is true when a function carries a decorator whose target is name, bare or called."""
    try:
        from honest_check import has_decorator
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import has_decorator: {exc}"]

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
        got = has_decorator(ctx, fdef, case["name"])
        if got != case["expect"]:
            bad.append(
                f"has_decorator({case['source']!r}, {case['name']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
