"""Honest probe for honest-check's binding_keys (Scenario: binding_keys).

binding_keys returns the type names a `binding(...)` call binds — the keys of its
first-argument table (HC004, HC005). The cases parse a real `binding(...)` call
with honest-parse, hand the real call node to the function, and pin the type names
it must return, including the explicit empty case for a binding over an empty
table.

The scenario fixes the bound type names, not the container type (the .hd types the
return `any`), so the probe compares the names as a set.
"""

from honest_parse import parse, walk


def _binding_call(source):
    root = parse(source.encode("utf-8"), "python").root_node
    for node in walk(root):
        if node.type == "call":
            return node
    return None


def _ctx(source):
    return {
        "root": None,
        "nodes": [],
        "aliases": {},
        "roles": {},
        "source": source.encode("utf-8"),
        "path": "case.py",
        "rule_config": {},
    }


# Each case: a binding(...) call source, and the type names it binds.
_CASES = [
    {
        "source": 'binding({"color": "swatch", "size": "field"})\n',
        "expect": {"color", "size"},
    },
    {
        # Absence: a binding over an empty table binds no type names.
        "source": "binding({})\n",
        "expect": set(),
    },
]


def probe_binding_keys():
    """binding_keys returns the keys of a binding(...) call's first-argument table."""
    try:
        from honest_check import binding_keys
    except ImportError as exc:
        return [f"cannot import binding_keys: {exc}"]

    bad = []
    for case in _CASES:
        call = _binding_call(case["source"])
        if call is None:
            bad.append(f"test setup: no call node in {case['source']!r}")
            continue
        got = binding_keys(_ctx(case["source"]), call)
        try:
            got_set = set(got)
        except TypeError:
            bad.append(f"binding_keys({case['source']!r}) -> {got!r}, not iterable of names")
            continue
        if got_set != case["expect"]:
            bad.append(
                f"binding_keys({case['source']!r}) -> {got_set!r}, expected {case['expect']!r}"
            )
    return bad
