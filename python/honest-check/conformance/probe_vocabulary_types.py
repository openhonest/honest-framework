"""Honest probe for honest-check's vocabulary_types (feature Scenario: vocabulary_types).

Scenario: vocabulary_types returns the type surface of a vocabulary(...) call — its
base-type names, its composed-type names, the base names its composed types require,
and the base names its composed types capture — reading the first-argument
dictionary through base_types_of (HC004, HC005).

What the probe can pin: the base-type names are the string keys of the vocabulary
call's first-argument dict (the scenario and the .hd both say base_types_of reads
the first-argument dictionary). The probe parses `vocabulary({"int": is_int,
"str": is_str})` and confirms both base-type names appear in the returned surface,
reading the surface by collecting every string it contains — a shape-neutral read.
A stub returning an empty surface contains neither name and fails.

What the probe cannot pin, and does NOT guess (see GAPS): the four-component
container shape (dict keys? tuple order?), and the composed-type surface — the
scenario names "composed-type names", "require" and "capture" but gives no concrete
composed-type input syntax, so no composed case is encoded here.

honest-parse is built; the vocabulary call is a real tree-sitter node.
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


def _vocab_call(ctx):
    for node in ctx["nodes"]:
        if node.type == "call":
            return node
    return None


def _strings_in(obj, seen=None):
    """Every str reachable inside a surface of nested dicts/lists/tuples/sets."""
    if seen is None:
        seen = set()
    if isinstance(obj, str):
        seen.add(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _strings_in(k, seen)
            _strings_in(v, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            _strings_in(item, seen)
    return seen


_SRC = 'c = vocabulary({"int": is_int, "str": is_str})\n'
_EXPECT_BASE = {"int", "str"}  # the first-argument dict's string keys


def probe_vocabulary_types():
    """vocabulary_types' surface includes the base-type names (the first-arg dict keys)."""
    try:
        from honest_check import vocabulary_types
    except ImportError as exc:
        return [f"cannot import vocabulary_types: {exc}"]

    bad = []
    ctx = _ctx(_SRC)
    surface = vocabulary_types(ctx, _vocab_call(ctx))
    present = _strings_in(surface)
    missing = _EXPECT_BASE - present
    if missing:
        bad.append(
            f"vocabulary_types base-type names missing {sorted(missing)} "
            f"from surface {surface!r}"
        )
    return bad
