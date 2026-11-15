"""Honest probe for honest-check's literal_string (feature Scenario: literal_string).

Scenario: given a `string` node, literal_string returns the Python string that
node spells, with its quotes stripped. Each case gives a one-expression snippet,
parsed under the real Python grammar; the probe hands the parsed `string` node to
the real function and pins the exact unquoted text it must spell. Double- and
single-quoted forms are both "quotes", and the empty string "" strips to "".

honest-parse is built; the node is a real tree-sitter node from a real parse,
never fabricated.
"""

from honest_parse import parse, walk

# Each case: the source the string node is parsed from, and the exact Python
# string literal_string must return once its quotes are stripped.
_CASES = [
    {"src": '"hello"', "expect": "hello"},   # double quotes stripped
    {"src": "'world'", "expect": "world"},   # single quotes stripped
    {"src": '""', "expect": ""},             # the empty string strips to ""
]


def _string_node(src):
    """The first `string` node in a parsed snippet, a real tree-sitter node."""
    root = parse(src.encode(), "python").root_node
    for node in walk(root):
        if node.type == "string":
            return node
    return None


def probe_literal_string():
    """literal_string spells a string node's Python string with its quotes stripped."""
    try:
        from honest_check import literal_string
    except ImportError as exc:
        return [f"cannot import literal_string: {exc}"]

    bad = []
    for case in _CASES:
        node = _string_node(case["src"])
        if node is None:
            bad.append(f"no string node parsed from {case['src']!r}")
            continue
        got = literal_string(node)
        if got != case["expect"]:
            bad.append(
                f"literal_string({case['src']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
