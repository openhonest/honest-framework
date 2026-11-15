"""Honest probe for honest-check's is_main_guard (Scenario: is_main_guard).

is_main_guard returns true when an `if` node is exactly the script guard
`if __name__ == "__main__":` — the one `if` HC-P001 exempts — and false for any
other `if`, which fires on the keyword alone. An elif_clause is never the guard.
The cases parse real Python with honest-parse, build a real CheckContext, and
hand the real node to the function: the guard if_statement (true), an ordinary
`if x == 1` if_statement (false), and an elif_clause carrying the guard
comparison (false, because an elif is never the guard).
"""

# Each case: a real source, the grammar type of the node handed in, and whether
# is_main_guard must call it the script guard.
_CASES = [
    {
        "source": "if __name__ == \"__main__\":\n    pass\n",
        "node_type": "if_statement",
        "expect": True,
    },
    {
        "source": "if x == 1:\n    pass\n",
        "node_type": "if_statement",
        "expect": False,
    },
    {
        # An elif carrying the guard comparison is a separate node, never the guard.
        "source": "if a:\n    pass\nelif __name__ == \"__main__\":\n    pass\n",
        "node_type": "elif_clause",
        "expect": False,
    },
]


def probe_is_main_guard():
    """is_main_guard is true only for the if_statement `if __name__ == \"__main__\":`."""
    try:
        from honest_check import is_main_guard
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import is_main_guard: {exc}"]

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
        node = None
        for candidate in walk(root):
            if candidate.type == case["node_type"]:
                node = candidate
                break
        if node is None:
            bad.append(f"test setup: no {case['node_type']} node in {case['source']!r}")
            continue
        got = is_main_guard(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"is_main_guard({case['source']!r}, <{case['node_type']}>) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
