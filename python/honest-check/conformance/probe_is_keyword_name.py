"""Honest probe for honest-check's is_keyword_name (feature Scenario: is_keyword_name).

Scenario: is_keyword_name returns true when an identifier is a keyword argument's
name — the `k` in f(k=v) — which names a parameter of the callee, not a global
read. Each case gives a snippet parsed under the real Python grammar and names
which identifier to pick: the `k` name is true, the `v` value is a global read
and is false, and a bare `k` read is false.

honest-parse is built; each identifier is a real tree-sitter node picked by field
from a real parse, never fabricated.
"""

from honest_parse import parse, walk

# Each case: the snippet, the parent node type to find, the field to pick off it
# (None picks the found node itself), and whether that identifier is a keyword
# argument's name.
_CASES = [
    # The `k` of f(k=v): the keyword argument's name.
    {"src": "f(k=v)", "parent": "keyword_argument", "field": "name", "expect": True},
    # The `v` of f(k=v): the argument's value, a global read, not a keyword name.
    {"src": "f(k=v)", "parent": "keyword_argument", "field": "value", "expect": False},
    # A bare `k` read: a plain global read, not a keyword argument's name.
    {"src": "k", "parent": "identifier", "field": None, "expect": False},
]


def _pick(src, parent_type, field):
    """The field child of the first `parent_type` node, or that node itself when
    field is None. A real tree-sitter node from a real parse."""
    root = parse(src.encode(), "python").root_node
    for node in walk(root):
        if node.type == parent_type:
            return node.child_by_field_name(field) if field else node
    return None


def probe_is_keyword_name():
    """is_keyword_name is true only for the name of a keyword argument."""
    try:
        from honest_check import is_keyword_name
    except ImportError as exc:
        return [f"cannot import is_keyword_name: {exc}"]

    bad = []
    for case in _CASES:
        node = _pick(case["src"], case["parent"], case["field"])
        if node is None:
            bad.append(f"no {case['parent']}/{case['field']} node parsed from {case['src']!r}")
            continue
        got = is_keyword_name(node)
        if got != case["expect"]:
            bad.append(
                f"is_keyword_name({case['src']!r}, {case['field']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
