"""Honest probe for honest-check's param_names (feature Scenario: param_names).

param_names reads the names a single parameter node binds: a bare identifier
(`x`), or the `name` of a typed (`x: int`) or defaulted (`x=5`) parameter — and
binds nothing for a splat (`*args`) or other shape.

Nodes are real tree-sitter nodes parsed by honest-parse; none is fabricated. For
each case the probe parses `def f(<param>): pass` and hands the one parameter
node to param_names.

Container caveat: the scenario fixes WHICH names a parameter binds, not whether
param_names returns them as a list, a set, or something else. This probe reads
the return as a list in source order (the string_members convention). See GAPS.
"""

from honest_parse import parse, walk


def _param_node(param_src):
    root = parse(f"def f({param_src}): pass".encode(), "python").root_node
    params = [n for n in walk(root) if n.type == "parameters"][0]
    return params.named_children[0]


# Each case: one parameter's source, and the names param_names must report it binds.
_CASES = [
    {"param": "x", "expect": ["x"]},        # bare identifier
    {"param": "x: int", "expect": ["x"]},   # typed parameter binds its name
    {"param": "x=5", "expect": ["x"]},      # defaulted parameter binds its name
    {"param": "*args", "expect": []},       # splat binds nothing here
]


def probe_param_names():
    """param_names returns the names a parameter binds, empty for a splat or other shape."""
    try:
        from honest_check import param_names
    except ImportError as exc:
        return [f"cannot import param_names: {exc}"]

    bad = []
    for case in _CASES:
        node = _param_node(case["param"])
        got = param_names(node)
        if got != case["expect"]:
            bad.append(
                f"param_names(<{case['param']!r}>) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
