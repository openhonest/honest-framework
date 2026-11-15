"""Honest probe for honest-check's call_arguments (feature Scenario: call_arguments).

call_arguments reads a call's positional argument nodes and its
keyword-name-to-value-node map. The probe parses a real call, calls the real
function, then reads each returned node's source text to compare against the
fixed expected positions and keyword bindings. Nodes are real tree-sitter nodes
parsed by honest-parse; none is fabricated.

call_arguments returns a CallArgs record (the .hd type): {positionals: list<Node>,
keywords: dict<str, Node>}. This probe reads result["positionals"] and
result["keywords"]. A result of a different shape is reported as
a failure string rather than crashing. See GAPS.
"""

from honest_parse import parse, walk


def _ctx(src):
    root = parse(src.encode(), "python").root_node
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": src.encode(),
        "path": "probe.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def _first_call(ctx):
    for node in ctx["nodes"]:
        if node.type == "call":
            return node
    return None


# Each case: a call snippet, its positional arg texts in order, and its
# keyword-name-to-value-text map.
_CASES = [
    {"src": "f(a, b, k=c)", "pos": ["a", "b"], "kw": {"k": "c"}},
    {"src": "h(x, y=z, w=1)", "pos": ["x"], "kw": {"y": "z", "w": "1"}},
    {"src": "g()", "pos": [], "kw": {}},  # absence: a call with no arguments
]


def probe_call_arguments():
    """call_arguments returns a call's positional nodes and its keyword-name-to-value-node map."""
    try:
        from honest_check import call_arguments
    except ImportError as exc:
        return [f"cannot import call_arguments: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        node = _first_call(ctx)
        result = call_arguments(ctx, node)
        try:
            positionals = result["positionals"]
            keywords = result["keywords"]
            got_pos = [n.text.decode() for n in positionals]
            got_kw = {k: v.text.decode() for k, v in keywords.items()}
        except (KeyError, TypeError, AttributeError) as exc:
            bad.append(
                f"call_arguments(<{case['src']!r}>) -> {result!r}, "
                f"not a CallArgs record with positionals and keywords: {exc}"
            )
            continue
        if got_pos != case["pos"] or got_kw != case["kw"]:
            bad.append(
                f"call_arguments(<{case['src']!r}>) -> positionals {got_pos}, keywords {got_kw}; "
                f"expected positionals {case['pos']}, keywords {case['kw']}"
            )
    return bad
