"""Honest probe for honest-check's is_boundary_decorator (Scenario: is_boundary_decorator).

is_boundary_decorator returns true when a decorator declares its function a
boundary — @boundary (bare or called) or @link(boundary=True). The cases parse
real Python with honest-parse, build a real CheckContext, hand the real
decorator node to the function, and pin true for the three boundary-declaring
shapes and false for decorators that do not declare a boundary — @link()
without the keyword, @link(boundary=False), and @orchestrator.
"""

# Each case: a real one-decorator source and whether is_boundary_decorator must
# call it a boundary declaration.
_CASES = [
    {"source": "@boundary\ndef f():\n    pass\n", "expect": True},
    {"source": "@boundary()\ndef f():\n    pass\n", "expect": True},
    {"source": "@link(boundary=True)\ndef f():\n    pass\n", "expect": True},
    {"source": "@link(boundary=False)\ndef f():\n    pass\n", "expect": False},
    {"source": "@link()\ndef f():\n    pass\n", "expect": False},
    {"source": "@orchestrator\ndef f():\n    pass\n", "expect": False},
]


def probe_is_boundary_decorator():
    """is_boundary_decorator is true for @boundary (bare/called) and @link(boundary=True) only."""
    try:
        from honest_check import is_boundary_decorator
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import is_boundary_decorator: {exc}"]

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
        decorator = None
        for node in walk(root):
            if node.type == "decorator":
                decorator = node
                break
        if decorator is None:
            bad.append(f"test setup: no decorator node in {case['source']!r}")
            continue
        got = is_boundary_decorator(ctx, decorator)
        if got != case["expect"]:
            bad.append(
                f"is_boundary_decorator({case['source']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
