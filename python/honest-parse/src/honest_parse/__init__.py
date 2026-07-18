"""Source parsing via tree-sitter — the shared parsing boundary of the Honest Framework.

This is the single place tree-sitter is touched. honest-check (the linter) and honest-test
(predicate AST classification) both depend on it rather than on tree-sitter directly, so the
framework has exactly one parsing mechanism. It owns the grammar handles and the small set of
node helpers consumers share. Grammar handles live in a table keyed by language, so adding a
target language is adding a row, not branching control flow.
"""

import types

import tree_sitter_css as ts_css
import tree_sitter_elixir as ts_elixir
import tree_sitter_go as ts_go
import tree_sitter_honest_hd as ts_hd
import tree_sitter_honest_jinja as ts_jinja
import tree_sitter_html as ts_html
import tree_sitter_javascript as ts_javascript
import tree_sitter_php as ts_php
import tree_sitter_python as ts_python
import tree_sitter_ruby as ts_ruby
from tree_sitter import Language, Parser

# Compiled grammars are immutable. They are exposed only through a read-only mapping
# (MappingProxyType), so there is no module-level mutable container here at all. A tree-sitter
# Parser carries internal state, so one is built per call rather than held as a shared
# singleton — `parse` stays free of hidden cross-call state. Each grammar occupies one row; adding
# a language is adding a row, never branching control flow. The six source languages honest-check
# and honest-test lint (python, javascript, ruby, php, go, elixir) are joined by the HTML/HTMX
# template grammar the single parser must also read, so no channel into an application is opaque
# (framework spec, "The input boundary is closed"). The PHP grammar exposes its handle as
# `language_php()` (the tag-aware grammar that accepts `<?php`), not `language()`, named explicitly.
# The `jinja` grammar (honest-parse's own `tree-sitter-honest-jinja`) is the template grammar the HTML
# grammar cannot supply: tree-sitter-html reads Jinja `{% %}` tags as opaque text, so a second grammar
# surfaces `{% include %}`/`{% extends %}` targets for honest-check's reference resolution (HC-REF002).
# The `css` grammar reads component stylesheets so honest-check can resolve a `class` reference against the
# rules a stylesheet defines (HC-REF003, the honest-components BEM contract). The `hd` grammar
# (honest-parse's own `tree-sitter-honest-hd`) parses the framework's `.hd` architecture-declaration
# files; honest-design's reader folds the resulting tree into the language-agnostic IR.
_LANGUAGES = types.MappingProxyType(
    {
        "python": Language(ts_python.language()),
        "javascript": Language(ts_javascript.language()),
        "ruby": Language(ts_ruby.language()),
        "php": Language(ts_php.language_php()),
        "go": Language(ts_go.language()),
        "elixir": Language(ts_elixir.language()),
        "html": Language(ts_html.language()),
        "jinja": Language(ts_jinja.language()),
        "css": Language(ts_css.language()),
        "hd": Language(ts_hd.language()),
    }
)


def parse(source: bytes, language: str):
    """Parse source bytes in the named language; return the tree-sitter tree."""
    return Parser(_LANGUAGES[language]).parse(source)


def parse_python(source: bytes):
    """Convenience wrapper for the Python grammar."""
    return parse(source, "python")


def parse_javascript(source: bytes):
    """Convenience wrapper for the JavaScript grammar."""
    return parse(source, "javascript")


def parse_ruby(source: bytes):
    """Convenience wrapper for the Ruby grammar."""
    return parse(source, "ruby")


def parse_php(source: bytes):
    """Convenience wrapper for the PHP grammar."""
    return parse(source, "php")


def parse_go(source: bytes):
    """Convenience wrapper for the Go grammar."""
    return parse(source, "go")


def parse_elixir(source: bytes):
    """Convenience wrapper for the Elixir grammar."""
    return parse(source, "elixir")


def parse_html(source: bytes):
    """Convenience wrapper for the HTML/HTMX template grammar."""
    return parse(source, "html")


def parse_jinja(source: bytes):
    """Convenience wrapper for the Jinja template grammar (surfaces {% include %}/{% extends %} targets)."""
    return parse(source, "jinja")


def parse_css(source: bytes):
    """Convenience wrapper for the CSS grammar (surfaces the class selectors a stylesheet defines)."""
    return parse(source, "css")


def parse_hd(source: bytes):
    """Convenience wrapper for the .hd architecture-declaration grammar (honest-design's read path)."""
    return parse(source, "hd")


def node_text(node, source: bytes) -> str:
    """The source slice a node spans, decoded as UTF-8."""
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def line_col(node) -> tuple[int, int]:
    """1-based (line, column) for a node's start."""
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
