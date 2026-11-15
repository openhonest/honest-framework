"""Honest probe for honest-check's canonical_name (feature Scenario: canonical_name).

canonical_name reads the framework constructor name a call resolves to: a direct
constructor-name call (`vocabulary({...})` -> "vocabulary"), or an aliased one
resolved through the import alias map in the context (`v({...})` with alias
v -> vocabulary -> "vocabulary"), and NOTHING (None) when the call is not a
framework constructor (section 3.3).

Nodes are real tree-sitter nodes parsed by honest-parse; none is fabricated.
The alias map is supplied on the context's `aliases` field, the honest_type
import-alias map build_context resolves.
"""

from honest_parse import parse, walk


def _ctx(src, aliases):
    root = parse(src.encode(), "python").root_node
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": aliases,
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


# Each case: a call snippet, the import-alias map in context, and the constructor
# name canonical_name must resolve the call to (or None when it is no constructor).
_CASES = [
    {"src": "vocabulary({})", "aliases": {}, "expect": "vocabulary"},        # direct constructor name
    {"src": "v({})", "aliases": {"v": "vocabulary"}, "expect": "vocabulary"},  # aliased, resolved through import
    {"src": "print(x)", "aliases": {}, "expect": None},                      # not a framework constructor -> NOTHING
]


def probe_canonical_name():
    """canonical_name resolves a call to its framework constructor name (direct or aliased), else None."""
    try:
        from honest_check import canonical_name
    except ImportError as exc:
        return [f"cannot import canonical_name: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"], case["aliases"])
        node = _first_call(ctx)
        got = canonical_name(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"canonical_name(<{case['src']!r}>, aliases={case['aliases']}) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
