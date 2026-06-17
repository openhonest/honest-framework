"""Tree-sitter parse layer (spec §3).

honest-check parses with tree-sitter, one grammar stack, so the same rule
logic ports across the framework's language implementations (Python, then
JavaScript, Ruby, Go). Rules operate on tree-sitter nodes via the helpers
here, never on a language-locked AST.

A new language is added by registering its grammar callable in `_GRAMMARS`;
the traversal helpers are language-agnostic.
"""
from __future__ import annotations

from typing import Iterator

import tree_sitter_python
from tree_sitter import Language, Node, Parser

# language name -> zero-arg callable returning the grammar pointer
_GRAMMARS = {
    "python": tree_sitter_python.language,
}

_LANGUAGES: dict[str, Language] = {}   # lazy cache, built on first use


def _language(name: str) -> Language:
    cached = _LANGUAGES.get(name)
    if cached is not None:
        return cached
    grammar = _GRAMMARS.get(name)
    if grammar is None:
        raise ValueError(
            f"no tree-sitter grammar registered for language {name!r}; "
            f"known: {sorted(_GRAMMARS)}"
        )
    lang = Language(grammar())
    _LANGUAGES[name] = lang
    return lang


def parse(source: str, language: str = "python"):
    """Parse source text into a tree-sitter tree."""
    parser = Parser(_language(language))
    return parser.parse(source.encode("utf-8"))


def source_bytes(source: str) -> bytes:
    return source.encode("utf-8")


def node_text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def descendants(node: Node) -> Iterator[Node]:
    """Pre-order traversal of node and all its descendants."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def find_by_type(node: Node, type_name: str) -> list[Node]:
    return [n for n in descendants(node) if n.type == type_name]


def named_children_of_type(node: Node, type_name: str) -> list[Node]:
    return [c for c in node.named_children if c.type == type_name]


def has_syntax_error(tree) -> bool:
    return tree.root_node.has_error


def line_of(node: Node) -> int:
    """1-based line number of a node's start."""
    return node.start_point[0] + 1


def col_of(node: Node) -> int:
    """1-based column of a node's start."""
    return node.start_point[1] + 1
