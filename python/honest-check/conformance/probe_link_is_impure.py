# scenario: link_is_impure
# inherits: hd=python/honest-check/honest-check.hd::link_is_impure -> feature=specs/features/honest-check.feature::link_is_impure
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
    {
        "source": "def f(config):\n    return config.cache\n",
        "watch": set(),
        "mutable_globals": {"cache"},
        "expect": False,
    },
    {
        "source": "def f():\n    return run(cache=1)\n",
        "watch": set(),
        "mutable_globals": {"cache"},
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

    expected_reads = [
        ("import os\ndef f():\n    return os.environ\n", "os.environ"),
        ("import sys\ndef f():\n    return sys.argv\n", "sys.argv"),
        ("import sys\ndef f():\n    return sys.argv[0]\n", "sys.argv"),
        ("import sys\ndef f():\n    return sys.version\n", "sys.version"),
        ("import sys\ndef f():\n    return sys.path\n", "sys.path"),
        ("def f():\n    return __file__\n", "__file__"),
        ("def f():\n    return __name__\n", "__name__"),
    ]
    excluded_reads = [
        ("def f():\n    return 'sys.argv'\n", "sys.argv"),
        ("def f(other):\n    return other.argv\n", "argv"),
        ("import sys\ndef f(argv):\n    sys.argv = argv\n", "sys.argv"),
        ("def f():\n    __file__ = 'path'\n", "__file__"),
        ("def f():\n    (__file__, label) = ('path', 'name')\n", "__file__"),
        ("def f():\n    __file__, label = ('path', 'name')\n", "__file__"),
        ("def f():\n    [__file__, label] = ['path', 'name']\n", "__file__"),
        ("def f():\n    label, *__file__ = ['path', 'name']\n", "__file__"),
        ("def f(paths):\n    for __file__ in paths:\n        pass\n", "__file__"),
        ("def f(paths):\n    return [0 for __file__ in paths]\n", "__file__"),
        ("def f():\n    return (__file__ := 'path')\n", "__file__"),
        ("def f(resource):\n    with resource as __file__:\n        pass\n", "__file__"),
        ("def f():\n    import pathlib as __file__\n", "__file__"),
        ("def f():\n    del __file__\n", "__file__"),
        ("def f():\n    global __file__\n", "__file__"),
        ("def outer():\n    __file__ = 'path'\n    def f():\n        nonlocal __file__\n", "__file__"),
        ("import sys\ndef f():\n    def inner():\n        return sys.argv\n    return inner\n", "sys.argv"),
        ("def f():\n    return lambda: __name__\n", "__name__"),
    ]
    read_cases = [
        {"source": source, "watch": {reference}, "mutable_globals": set(), "expect": True}
        for source, reference in expected_reads
    ]
    negative_cases = [
        {"source": source, "watch": {reference}, "mutable_globals": set(), "expect": False}
        for source, reference in excluded_reads
    ]

    other_language_cases = [
        {
            "source": "def f\n  puts('path')\nend\n",
            "watch": {"open"},
            "mutable_globals": set(),
            "expect": False,
            "language": "ruby",
            "path": "case.rb",
        },
        {
            "source": "function f() { return __file__; }",
            "watch": {"__file__"},
            "mutable_globals": set(),
            "expect": False,
            "language": "javascript",
            "path": "case.js",
        },
    ]

    bad = []
    for case in _CASES + read_cases + negative_cases + other_language_cases:
        tree = parse(case["source"].encode("utf-8"), case.get("language", "python"))
        root = tree.root_node
        nodes = walk(root)
        ctx = {
            "root": root,
            "nodes": nodes,
            "aliases": {},
            "roles": {},
            "source": root.text,
            "path": case.get("path", "case.py"),
            "rule_config": {},
        }
        fdef = next(
            (
                n
                for n in nodes
                if n.type in {"function_definition", "function_declaration", "method"}
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
