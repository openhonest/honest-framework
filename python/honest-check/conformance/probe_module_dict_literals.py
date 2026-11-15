"""Honest probe for honest-check's module_dict_literals (feature Scenario: module_dict_literals).

Scenario: module_dict_literals returns each module-scope name bound to a dict
literal, mapped to the set of string keys the literal declares; a name bound to
anything but a module-scope dict literal is not included (HC-HF002).

Two cases. The first module binds a handler dict at module scope alongside an
immutable and a dict inside a function (not module scope), and pins the one mapping
to its string-key set. The second module binds no dict at all — the explicit
absence case — and pins the empty mapping. honest-parse is built; every node is a
real tree-sitter node.

Container caveat: the scenario fixes the names and their string-key sets, not the
outer dict type or the key-collection type. The probe normalises each value through
`set(...)`, so it holds for any keys collection. See GAPS.
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


# Case 1: HANDLERS is a module-scope dict literal; CONST is not a dict; `local`
# sits inside a function, not module scope — both excluded.
_SRC_PRESENT = (
    'HANDLERS = {"a": 1, "b": 2}\n'
    "CONST = 42\n"
    "def f():\n"
    '    local = {"z": 1}\n'
)
# Case 2: no module-scope dict literal at all — the explicit absence.
_SRC_ABSENT = "CONST = 42\nITEMS = [1, 2]\n"

_CASES = [
    {"src": _SRC_PRESENT, "expect": {"HANDLERS": {"a", "b"}}},
    {"src": _SRC_ABSENT, "expect": {}},  # absence: no module dict literal
]


def _normalise(mapping):
    return {name: set(keys) for name, keys in dict(mapping).items()}


def probe_module_dict_literals():
    """module_dict_literals maps each module-scope dict-literal name to its string-key set."""
    try:
        from honest_check import module_dict_literals
    except ImportError as exc:
        return [f"cannot import module_dict_literals: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        got = _normalise(module_dict_literals(ctx))
        if got != case["expect"]:
            bad.append(
                f"module_dict_literals(<module>) -> {got}, expected {case['expect']}"
            )
    return bad
