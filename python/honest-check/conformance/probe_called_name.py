"""Honest probe for honest-check's called_name (feature Scenario: called_name).

called_name reads the name a call invokes: a bare identifier (`foo` in
`foo(1)`), or the final attribute of a dotted call (`addEventListener` in
`window.addEventListener(e)`), and NOTHING (None) when the call target is
neither — a call on a call's result such as `get()(1)` (HC-P011).

Nodes are real tree-sitter nodes parsed by honest-parse; none is fabricated.
Each case pins a source snippet and the name the call in it resolves to.
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
    # walk lists parents before children, so the first call node is the
    # outermost call (for get()(1) that is the whole get()(1), whose
    # function part is itself a call).
    for node in ctx["nodes"]:
        if node.type == "call":
            return node
    return None


# Each case: a call source snippet, and the name called_name must return (or None).
_CASES = [
    {"src": "foo(1)", "expect": "foo"},                       # bare identifier
    {"src": "window.addEventListener(e)", "expect": "addEventListener"},  # final attribute
    {"src": "get()(1)", "expect": None},                      # call on a call's result -> NOTHING
]


def probe_called_name():
    """called_name returns the bare identifier or final dotted attribute a call invokes, else None."""
    try:
        from honest_check import called_name
    except ImportError as exc:
        return [f"cannot import called_name: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        node = _first_call(ctx)
        got = called_name(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"called_name(<{case['src']!r}>) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
