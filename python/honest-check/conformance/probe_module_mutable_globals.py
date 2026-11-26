# scenario: module_mutable_globals
# inherits: hd=python/honest-check/honest-check.hd::module_mutable_globals -> feature=specs/features/honest-check.feature::module_mutable_globals
"""Honest probe for honest-check's module_mutable_globals (feature Scenario: module_mutable_globals).

Scenario: module_mutable_globals returns the module-level names bound to a mutable
(or not provably immutable) value — the globals a read of which makes a link impure;
a name bound to an immutable value, and an imported or def/class name, are not
included (HC008).

The probe parses one module whose top level mixes every excluded kind with the two
mutable bindings, hands the real CheckContext to the function, and pins the exact
set of mutable-global names. honest-parse is built; every node is a real
tree-sitter node, never fabricated.

Container caveat: the scenario fixes WHICH names are mutable globals, not whether
the function returns them as a set, a list, or something else. The probe reads the
return through `set(...)`, so it holds for any names collection. See GAPS.
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


# One module source, and the module-level names bound to a not-provably-immutable
# value. CONST is immutable, os is imported, f is a def, C is a class — all excluded.
_SRC = (
    "import os\n"
    "CONST = 42\n"
    "CONST + increment()\n"
    "CACHE = {}\n"
    "ITEMS = []\n"
    "config.items = []\n"
    "register()\n"
    "REGISTERED = register()\n"
    "def f():\n    pass\n"
    "class C:\n    pass\n"
)
_EXPECT = {"CACHE", "ITEMS", "REGISTERED"}


def probe_module_mutable_globals():
    """module_mutable_globals returns exactly the module names bound to a mutable value."""
    try:
        from honest_check import module_mutable_globals
    except ImportError as exc:
        return [f"cannot import module_mutable_globals: {exc}"]

    bad = []
    ctx = _ctx(_SRC)
    got = module_mutable_globals(ctx)
    if set(got) != _EXPECT:
        bad.append(
            f"module_mutable_globals(<module>) -> {sorted(set(got))}, "
            f"expected {sorted(_EXPECT)}"
        )
    return bad
