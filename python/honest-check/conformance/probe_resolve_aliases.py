"""Honest probe for honest-check's resolve_aliases (feature Scenario: resolve_aliases).

resolve_aliases reads every import statement off a real parsed tree and returns the
map from each local name an honest-framework import bound to that import's canonical
framework name. A direct alias maps the bound name to the constructor name
(vocabulary as v -> {"v": "vocabulary"}); a module alias maps the dotted alias to
the dotted canonical module (import honest_type as ht -> {"ht.*": "honest_type.*"}),
exactly as the .hd writes it; a source that imports nothing from the framework
yields the empty map. Each case parses a real Python snippet with honest-parse and
feeds the real root node. A `return {}` stub passes only the no-import case.
"""

# Each case: a real Python snippet, and the alias map resolve_aliases must return.
_CASES = [
    # Direct alias: the bound local name maps to the canonical constructor name.
    {
        "source": b"from honest_type import vocabulary as v\n",
        "expect": {"v": "vocabulary"},
    },
    # Module alias: the dotted alias maps to the dotted canonical module.
    {
        "source": b"import honest_type as ht\n",
        "expect": {"ht.*": "honest_type.*"},
    },
    # Nothing framework imported: the empty map.
    {
        "source": b"import os\n",
        "expect": {},
    },
]


def probe_resolve_aliases():
    """resolve_aliases maps each framework-import local name to its canonical name."""
    try:
        from honest_check import resolve_aliases
    except ImportError as exc:
        return [f"cannot import resolve_aliases: {exc}"]
    try:
        from honest_parse import parse
    except ImportError as exc:
        return [f"cannot import honest_parse.parse: {exc}"]

    bad = []
    for case in _CASES:
        root = parse(case["source"], "python").root_node
        got = resolve_aliases(root=root, source=case["source"])
        if got != case["expect"]:
            bad.append(
                f"resolve_aliases({case['source']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
