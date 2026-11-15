"""Honest probe for honest-check's is_empty_default (feature Scenario: is_empty_default).

Scenario: is_empty_default returns true when a parameter's default stands for
absence rather than a baked-in value — None, False, a zero number, an empty
string, an empty list/dict/tuple literal, or an empty-constructor call — and
false for a populated literal or a non-zero number. Each case gives a function
definition whose single parameter carries the default under test, parsed under
the real Python grammar; the probe hands that default's value node (and a real
CheckContext from the same parse) to the real function and pins the boolean.

honest-parse is built; the default value node is the real tree-sitter `value`
child of a real default_parameter, never fabricated.
"""

from honest_parse import parse, walk

# Each case: the default expression a parameter carries, and whether it stands
# for absence (true) rather than a baked-in value (false).
_CASES = [
    {"default": "None", "expect": True},       # None
    {"default": "False", "expect": True},      # False
    {"default": "0", "expect": True},          # a zero number
    {"default": '""', "expect": True},         # an empty string
    {"default": "[]", "expect": True},         # an empty list literal
    {"default": "{}", "expect": True},         # an empty dict literal
    {"default": "()", "expect": True},         # an empty tuple literal
    {"default": "list()", "expect": True},     # an empty-constructor call
    {"default": "dict()", "expect": True},     # an empty-constructor call
    {"default": "[1]", "expect": False},       # a populated literal
    {"default": "30", "expect": False},        # a non-zero number
    {"default": '"text"', "expect": False},    # a populated (non-empty) string literal
]


def _ctx_and_default(default_src):
    """A real CheckContext and the `value` node of a parameter's default.

    The default is parsed inside a real function definition, so the value node is
    a genuine default_parameter child; the context is built from the same parse.
    """
    src = f"def f(x={default_src}): pass"
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
    for node in walk(root):
        if node.type == "default_parameter":
            return ctx, node.child_by_field_name("value")
    return ctx, None


def probe_is_empty_default():
    """is_empty_default is true exactly for defaults that stand for absence."""
    try:
        from honest_check import is_empty_default
    except ImportError as exc:
        return [f"cannot import is_empty_default: {exc}"]

    bad = []
    for case in _CASES:
        ctx, node = _ctx_and_default(case["default"])
        if node is None:
            bad.append(f"no default value node parsed from default {case['default']!r}")
            continue
        got = is_empty_default(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"is_empty_default(default={case['default']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
