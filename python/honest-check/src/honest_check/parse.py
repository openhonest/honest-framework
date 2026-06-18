"""Source parsing via tree-sitter — the single parsing boundary (section 3).

honest-check reads abstract syntax trees, never executes application code. This
module owns the tree-sitter handle and the small set of node helpers the rules
share, so rule modules depend on these helpers rather than on tree-sitter
directly. The grammar handles live in a table keyed by language so adding a
target language is adding a row, not branching control flow.
"""

import types

import tree_sitter_python as ts_python
from tree_sitter import Language, Parser

# Compiled grammars are immutable. They are exposed only through a read-only
# mapping (MappingProxyType), so there is no module-level mutable container here at
# all. A tree-sitter Parser carries internal state, so one is built per call rather
# than held as a shared singleton — `parse` stays free of hidden cross-call state.
_LANGUAGES = types.MappingProxyType(
    {
        "python": Language(ts_python.language()),
    }
)


def parse(source: bytes, language: str):
    """Parse source bytes in the named language; return the tree-sitter tree."""
    return Parser(_LANGUAGES[language]).parse(source)


def parse_python(source: bytes):
    """Convenience wrapper for the Python grammar."""
    return parse(source, "python")


def node_text(node, source: bytes) -> str:
    """The source slice a node spans, decoded as UTF-8."""
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def line_col(node) -> tuple[int, int]:
    """1-based (line, column) for a node's start, per section 6.1."""
    row, col = node.start_point
    return row + 1, col + 1


def walk(node):
    """Yield every node in the subtree, depth-first, parents before children."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def first_error_node(root):
    """The first ERROR or MISSING node in the tree, or None if the tree is clean."""
    for node in walk(root):
        if node.is_error or node.is_missing:
            return node
    return None
