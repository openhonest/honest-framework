"""Honest probe for honest-check's nonlocal_names (Scenario: nonlocal_names).

nonlocal_names returns the names declared by the `nonlocal` statements directly
in a function body. The cases parse real Python with honest-parse, hand the real
body statement nodes to the function, and pin the names it must report, including
the explicit empty case for a body carrying no `nonlocal` statement.

The scenario fixes the declared names, not the container type (the .hd types the
return `any`), so the probe compares the names as a set.
"""

from honest_parse import parse, walk


def _body_statements(source):
    root = parse(source.encode("utf-8"), "python").root_node
    for node in walk(root):
        if node.type == "block":
            return list(node.named_children)
    return []


# Each case: real source, and the set of names its `nonlocal` statements declare.
_CASES = [
    {
        # Two nonlocal statements, three names, plus a non-nonlocal statement.
        "source": "def f():\n    nonlocal a\n    nonlocal b, c\n    d = 1\n",
        "expect": {"a", "b", "c"},
    },
    {
        # Absence: a body with no nonlocal statement declares no names.
        "source": "def g():\n    d = 1\n",
        "expect": set(),
    },
]


def probe_nonlocal_names():
    """nonlocal_names reports every name the body's `nonlocal` statements declare."""
    try:
        from honest_check import nonlocal_names
    except ImportError as exc:
        return [f"cannot import nonlocal_names: {exc}"]

    bad = []
    for case in _CASES:
        statements = _body_statements(case["source"])
        got = nonlocal_names(statements)
        try:
            got_set = set(got)
        except TypeError:
            bad.append(f"nonlocal_names({case['source']!r}) -> {got!r}, not iterable of names")
            continue
        if got_set != case["expect"]:
            bad.append(
                f"nonlocal_names({case['source']!r}) -> {got_set!r}, expected {case['expect']!r}"
            )
    return bad
