"""Honest probe for honest-check's local_function_links (Scenario: local_function_links).

local_function_links maps each function defined in this file to whether it carries a
`@link` decorator (HC001), so a chain positional resolving to one of these names is a
local link declaration honest-check can read. Each case parses real Python with
honest-parse and builds a real CheckContext.

The two-function case pins a concrete non-empty map: the @link-decorated function maps
true, the undecorated one maps false. The no-function case is the explicit empty-map
boundary. A `return {}` stub passes the empty case but fails the two-function case.
"""

# Each case: a real source, and the name-to-has-@link map local_function_links must return.
_CASES = [
    {
        "source": "@link\ndef classify_card(x):\n    return x\n\ndef helper(y):\n    return y\n",
        "expect": {"classify_card": True, "helper": False},
    },
    # Boundary: a file defining no function yields the empty map.
    {"source": "x = 1\n", "expect": {}},
]


def probe_local_function_links():
    """local_function_links maps each file-local function to whether it carries a @link decorator."""
    try:
        from honest_check import local_function_links
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import local_function_links: {exc}"]

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
        got = local_function_links(ctx)
        if got != case["expect"]:
            bad.append(
                f"local_function_links({case['source']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
