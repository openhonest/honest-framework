"""Honest probe for honest-check's link_is_impure (Scenario: link_is_impure).

link_is_impure is true when a link's own body calls a watched function or reads a
module-level mutable global, and the body search does not descend into a nested def
or lambda (HC008). Each case parses real Python with honest-parse, builds a real
CheckContext, finds the real function_definition for the link, and hands it the
watch list and the mutable-global set.

One case pins impurity through a watched call, one through a mutable-global read,
one pins a pure link false, and the nested-def case pins false because the watched
call lives in an inner scope the search does not descend into. A `return False`
stub fails the two true cases; a `return True` stub fails the two false cases.
"""

# Each case: a real source defining a link `f`, the watch list, the module-level
# mutable globals, and whether link_is_impure must flag f.
_CASES = [
    # Impure: f's own body calls a watched function.
    {
        "source": "def f():\n    open('x')\n",
        "watch": {"open"},
        "mutable_globals": set(),
        "expect": True,
    },
    # Impure: f's own body reads a module-level mutable global.
    {
        "source": "def f():\n    return CACHE\n",
        "watch": set(),
        "mutable_globals": {"CACHE"},
        "expect": True,
    },
    # Pure: f calls nothing watched and reads no mutable global; x is a local.
    {
        "source": "def f(x):\n    return x + 1\n",
        "watch": {"open"},
        "mutable_globals": {"CACHE"},
        "expect": False,
    },
    # Not descended: the watched call lives in nested def g, not f's own body.
    {
        "source": "def f():\n    def g():\n        open('x')\n    return 1\n",
        "watch": {"open"},
        "mutable_globals": set(),
        "expect": False,
    },
]


def probe_link_is_impure():
    """link_is_impure is true for a watched call or mutable-global read in the link's own body only."""
    try:
        from honest_check import link_is_impure
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import link_is_impure: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "python")
        root = tree.root_node
        nodes = walk(root)
        ctx = {
            "root": root,
            "nodes": nodes,
            "aliases": {},
            "roles": {},
            "source": root.text,
            "path": "case.py",
            "rule_config": {},
        }
        fdef = next(
            (
                n
                for n in nodes
                if n.type == "function_definition"
                and n.named_children
                and n.named_children[0].text.decode("utf-8") == "f"
            ),
            None,
        )
        if fdef is None:
            bad.append(f"test setup: no function_definition named 'f' in {case['source']!r}")
            continue
        got = link_is_impure(ctx, fdef, case["watch"], case["mutable_globals"])
        if bool(got) != case["expect"]:
            bad.append(
                f"link_is_impure({case['source']!r}, watch={case['watch']}, "
                f"mutable_globals={case['mutable_globals']}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
