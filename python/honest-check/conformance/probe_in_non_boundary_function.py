"""Honest probe for honest-check's in_non_boundary_function (Scenario: in_non_boundary_function).

in_non_boundary_function is true when a node's nearest enclosing function exists,
carries no boundary decorator, and the declaration gives its name no door role —
the interior scope HC-P002/HC-P004/HC-P005 fire in — and false at module scope or
inside a boundary function. Each case parses real Python with honest-parse, builds
a real CheckContext (the roles map carries the declared function-to-role data), and
hands the real inner `call` node to the function.

The interior case pins true; module scope, an @boundary decorator, and a declared
door role each pin false. A `return False` stub passes the three false cases but
fails the interior case; a `return True` stub fails all three false cases.
"""

# Each case: a real source, the declared role map, and whether a node inside the
# body's first call sits in a non-boundary (interior) function.
_CASES = [
    # Interior: plain function, no decorator, no declared role.
    {"source": "def f():\n    open('x')\n", "roles": {}, "expect": True},
    # Module scope: the call has no enclosing function at all.
    {"source": "open('x')\n", "roles": {}, "expect": False},
    # Boundary decorator: the enclosing function is declared a door in code.
    {"source": "@boundary\ndef f():\n    open('x')\n", "roles": {}, "expect": False},
    # Declared door role: the .hd gives f a door role, so its interior is a boundary.
    {"source": "def f():\n    open('x')\n", "roles": {"f": "boundary_in"}, "expect": False},
]


def probe_in_non_boundary_function():
    """in_non_boundary_function is true inside a plain function, false at module scope or in a door."""
    try:
        from honest_check import in_non_boundary_function
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import in_non_boundary_function: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "python")
        root = tree.root_node
        nodes = walk(root)
        ctx = {
            "root": root,
            "nodes": nodes,
            "aliases": {},
            "roles": case["roles"],
            "source": root.text,
            "path": "case.py",
            "rule_config": {},
        }
        node = next((n for n in nodes if n.type == "call"), None)
        if node is None:
            bad.append(f"test setup: no call node in {case['source']!r}")
            continue
        got = in_non_boundary_function(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"in_non_boundary_function({case['source']!r}, roles={case['roles']}) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
