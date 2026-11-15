"""Conformance probe for honest-check's feature_state_flag.

Scenario (specs/features/honest-check.feature, Scenario: feature_state_flag):
    Given ctx: CheckContext and call_node: Node
    When feature_state_flag is called
    Then it returns the flag a feature_state(state, "flag") call names - its second
    positional string literal - or NOTHING when the call names fewer than two positionals
    or a dynamic (non-literal) flag, the call resolved by name through called_name.

The probe parses each call with the real honest-parse grammar, builds a CheckContext over
it, hands the call node to the real function, and checks the returned flag (a str) or None
against the literal the scenario fixes.
"""

import honest_parse

# Each case: a snippet holding one feature_state call, and the flag it names (or None).
_CASES = [
    {"src": 'feature_state(x, "dark_mode")', "expect": "dark_mode"},   # second positional literal
    {"src": 'feature_state(x, "a", "b")', "expect": "a"},              # second positional, extra ignored
    {"src": "feature_state(x)", "expect": None},                       # fewer than two positionals
    {"src": "feature_state(x, flag)", "expect": None},                 # dynamic (non-literal) flag
]


def _ctx(src):
    source = src.encode("utf-8")
    tree = honest_parse.parse(source, "python")
    root = tree.root_node
    return {
        "root": root,
        "nodes": honest_parse.walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": "feature.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def _call_node(ctx):
    for node in ctx["nodes"]:
        if node.type == "call":
            return node
    return None


def probe_feature_state_flag():
    """A feature_state(state, "flag") call names its second positional string literal, or None for too-few or dynamic positionals."""
    try:
        from honest_check import feature_state_flag
    except ImportError as exc:
        return [f"cannot import feature_state_flag: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        call_node = _call_node(ctx)
        if call_node is None:
            bad.append(f"probe setup: no call node parsed from {case['src']!r}")
            continue
        try:
            got = feature_state_flag(ctx, call_node)
        except Exception as exc:
            bad.append(f"feature_state_flag({case['src']!r}) raised {exc!r}")
            continue
        if got != case["expect"]:
            bad.append(f"feature_state_flag({case['src']!r}) -> {got!r}, expected {case['expect']!r}")
    return bad
