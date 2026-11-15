"""Honest probe for honest-check's string_members (feature Scenario: string_members).

Scenario: given a set, list or tuple node, string_members returns the string
values that node holds, in source order. Each case gives a one-expression
snippet, parsed under the real Python grammar; the probe hands the parsed
container node (and a real CheckContext built from the same parse) to the real
function and pins the exact list of unquoted strings, in order. The empty list
literal is the absence case: a container holding no strings yields [].

honest-parse is built; the container node and the CheckContext come from a real
parse, never fabricated.
"""

from honest_parse import parse, walk

# Each case: the source the container node is parsed from, the node type to pick
# (set, list or tuple), and the string values string_members must return in order.
_CASES = [
    {"src": '{"a", "b"}', "container": "set", "expect": ["a", "b"]},
    {"src": '["x", "y"]', "container": "list", "expect": ["x", "y"]},
    {"src": '("p", "q")', "container": "tuple", "expect": ["p", "q"]},
    # Absence: a list literal holding no strings yields the empty list.
    {"src": "[]", "container": "list", "expect": []},
]


def _ctx_and_node(src, node_type):
    """A real CheckContext over `src` and the first node of `node_type` in it.

    The context is built from the same parse the node came from, so its source
    bytes align with the node's byte offsets.
    """
    root = parse(src.encode(), "python").root_node
    ctx = {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": src.encode(),
        "path": "snippet.py",
        "rule_config": {},
    }
    node = next((n for n in walk(root) if n.type == node_type), None)
    return ctx, node


def probe_string_members():
    """string_members returns a container's string values in source order."""
    try:
        from honest_check import string_members
    except ImportError as exc:
        return [f"cannot import string_members: {exc}"]

    bad = []
    for case in _CASES:
        ctx, node = _ctx_and_node(case["src"], case["container"])
        if node is None:
            bad.append(f"no {case['container']} node parsed from {case['src']!r}")
            continue
        got = string_members(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"string_members({case['src']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
