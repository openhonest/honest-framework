"""Source parsing via tree-sitter — the shared parsing boundary of the Honest Framework.

This is the single place tree-sitter is touched. honest-check (the checker) and honest-test
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


class UnknownGrammar(Exception):
    """A grammar name this module does not carry.

    Raised rather than returned because this is the boundary, the one place the principles put a
    typed exception. A bare KeyError from the table lookup names the missing key and nothing a
    caller can act on: not what was asked for, not what the module carries, not what to do instead.
    """


def parse(source: bytes, language: str):
    """Parse source bytes under the named grammar; return the tree-sitter tree."""
    if language not in _LANGUAGES:
        raise UnknownGrammar(
            f"no grammar named {language!r}; honest-parse carries {', '.join(sorted(_LANGUAGES))}"
        )
    return Parser(_LANGUAGES[language]).parse(source)












def line_col(node) -> tuple[int, int]:
    """1-based (line, column) for a node's start."""
    row, col = node.start_point
    return row + 1, col + 1


def walk(node):
    """Every node in the subtree, depth-first, parents before children.

    A list, not a generator: the card says `list<Node>` and a list reads the same twice, where a
    generator empties as it is read and hands a second reader an empty answer with no error
    (HC-R005). honest-check walks one tree with many rules, so the answer must survive a second
    read.
    """
    out = []
    stack = [node]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(reversed(current.children))
    return out


def first_error_node(root):
    """The first ERROR or MISSING node in the tree, or None if the tree is clean."""
    for node in walk(root):
        if node.is_error or node.is_missing:
            return node
    return None

# Section: the one chooser. The extension table is this module's own vocabulary, written out in
# full, and it is closed. An extension absent from it is a named failure, never a fall-back to the
# commonest grammar: reading a Ruby file under the Python grammar reports a clean parse, so the file
# passes every rule that reads its tree while nothing has actually read the file. Every grammar in
# _LANGUAGES is reachable through some row here, or a file of that language can never be read.
_LANGUAGE_BY_SUFFIX = types.MappingProxyType(
    {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".rb": "ruby",
        ".php": "php",
        ".go": "go",
        ".ex": "elixir",
        ".exs": "elixir",
        ".html": "html",
        ".htm": "html",
        ".jinja": "jinja",
        ".j2": "jinja",
        ".css": "css",
        ".hd": "hd",
    }
)


def language_of(path: str):
    """The grammar a path is read under, from the closed suffix table. ok(language), or err for a
    suffix the table does not carry. Pure."""
    for suffix, language in _LANGUAGE_BY_SUFFIX.items():
        if path.endswith(suffix):
            return {"ok": language}
    return {
        "err": {
            "code": "unplaceable_extension",
            "message": f"no grammar is declared for the extension of {path!r}; the table carries "
                       f"{', '.join(sorted(_LANGUAGE_BY_SUFFIX))}",
            "category": "client",
            "detail": {"path": path},
        }
    }


def place_source(source: bytes, path: str):
    """The tree for source read under the grammar its path names: ok(tree), or the chooser's err.

    The module's one orchestrator. It reads the extension through `language_of` and hands the
    language to `parse`, so the choice of grammar happens in one place and the world is touched in
    one other. It holds the routing and nothing else does.
    """
    language = language_of(path)
    if "ok" not in language:
        return language
    tree = parse(source, language["ok"])
    root = tree.root_node
    if root.has_error:
        error = first_error_node(root)
        line, col = line_col(error)
        return {
            "err": {
                "code": "syntax_error",
                "message": f"{path} does not parse under {language['ok']}: error at line {line}, column {col}",
                "category": "client",
                "detail": {"path": path, "line": line, "col": col},
            }
        }
    return {"ok": tree}


def parse_source(source: bytes, path: str):
    """The door: where a calling module arrives, and where its answer goes back.

    Thin, and I/O only. It hands the call to the one orchestrator and adds nothing of its own. This
    module writes nothing anywhere, so its work is consumed by travelling back through here, and a
    function declared as writing to the caller would be a false card: a return is not a write.
    """
    return place_source(source, path)


__all__ = [
    "UnknownGrammar",
    "first_error_node",
    "language_of",
    "line_col",
    "parse",
    "parse_source",
    "place_source",
    "walk",
]
