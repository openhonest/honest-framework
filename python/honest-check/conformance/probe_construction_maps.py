# scenario: construction_maps
# inherits: hd=python/honest-check/honest-check.hd::construction_maps -> feature=specs/features/honest-check.feature::construction_maps
"""Honest probe for honest-check's construction_maps (feature Scenario: construction_maps).

Scenario: construction_maps returns each file-local variable bound to a
vocabulary(...) or a binding(...) call, mapped to that construction call node; a
name bound to anything else, or one honest-check cannot resolve to those two
constructors, is not included (HC004, HC005).

The probe parses one module binding a vocabulary call, a binding call, an immutable,
and an unrelated call. It pins the mapped keys (the two construction names) and
checks each mapped value is the real construction call node, read back by its source
text. honest-parse is built; every node is a real tree-sitter node.

Container caveat: the scenario fixes the keys and that each maps to the right
construction call; the exact dict/node value identity is read through the node's
own source text (`.text`), which is scenario-neutral. See GAPS.
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


# x binds an immutable, y binds a non-constructor call — both excluded.
_SRC = (
    'v = vocabulary({"int": is_int})\n'
    'b = binding({"int": "slot"})\n'
    "x = 5\n"
    "pending: int\n"
    "y = other({})\n"
    "registry.v = vocabulary({})\n"
    "registry.b = binding({})\n"
    "register(v)\n"
    "names = []\n"
    "names += vocabulary({'part': {'one'}})\n"
)
_EXPECT_KEYS = {"v", "b"}
_EXPECT_TEXT = {"v": 'vocabulary({"int": is_int})', "b": 'binding({"int": "slot"})'}


def probe_construction_maps():
    """construction_maps maps each vocabulary/binding-bound name to its construction call node."""
    try:
        from honest_check import construction_maps
    except ImportError as exc:
        return [f"cannot import construction_maps: {exc}"]

    bad = []
    ctx = _ctx(_SRC)
    got = construction_maps(ctx)
    if set(got) != _EXPECT_KEYS:
        bad.append(
            f"construction_maps keys -> {sorted(set(got))}, expected {sorted(_EXPECT_KEYS)}"
        )
        return bad
    for name, want_text in _EXPECT_TEXT.items():
        node = got[name]
        got_text = node.text.decode() if hasattr(node, "text") else repr(node)
        if got_text != want_text:
            bad.append(
                f"construction_maps[{name!r}] -> {got_text!r}, expected {want_text!r}"
            )
    return bad
