"""Honest probe for honest-check's is_attribute_suffix (feature Scenario: is_attribute_suffix).

Scenario: is_attribute_suffix returns true when an identifier is the attribute
part of an `x.name` access, because reading config.timeout reads config, not a
global called timeout. Each case gives a snippet parsed under the real Python
grammar and names which identifier to pick: the `.timeout` attribute part is
true, the `config` object is false, and a bare `timeout` read is false.

honest-parse is built; each identifier is a real tree-sitter node picked by field
from a real parse, never fabricated.
"""

from honest_parse import parse, walk

# Each case: the snippet, the parent node type to find, the field to pick off it
# (None picks the found node itself), and whether that identifier is an
# attribute suffix.
_CASES = [
    # The `.timeout` suffix of config.timeout: the attribute part.
    {"src": "config.timeout", "parent": "attribute", "field": "attribute", "expect": True},
    # The `config` object of config.timeout: a read of config, not a suffix.
    {"src": "config.timeout", "parent": "attribute", "field": "object", "expect": False},
    # A bare `timeout` read: a plain global read, not an attribute suffix.
    {"src": "timeout", "parent": "identifier", "field": None, "expect": False},
]


def _pick(src, parent_type, field):
    """The field child of the first `parent_type` node, or that node itself when
    field is None. A real tree-sitter node from a real parse."""
    root = parse(src.encode(), "python").root_node
    for node in walk(root):
        if node.type == parent_type:
            return node.child_by_field_name(field) if field else node
    return None


def probe_is_attribute_suffix():
    """is_attribute_suffix is true only for the attribute part of an x.name access."""
    try:
        from honest_check import is_attribute_suffix
    except ImportError as exc:
        return [f"cannot import is_attribute_suffix: {exc}"]

    bad = []
    for case in _CASES:
        node = _pick(case["src"], case["parent"], case["field"])
        if node is None:
            bad.append(f"no {case['parent']}/{case['field']} node parsed from {case['src']!r}")
            continue
        got = is_attribute_suffix(node)
        if got != case["expect"]:
            bad.append(
                f"is_attribute_suffix({case['src']!r}, {case['field']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
