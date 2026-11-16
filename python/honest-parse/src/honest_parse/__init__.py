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


# Lazy two-row boolean dispatch. The table holds the two selectors; _pick looks a flag up and runs
# only the chosen thunk, so a branch becomes a lookup (HC-P001) and the unchosen side never runs.
_TWO_ROW = {True: lambda t, f: t, False: lambda t, f: f}


def _pick(flag, when_true, when_false):
    """Run the thunk the flag selects and return its result; the other thunk never runs."""
    return _TWO_ROW[bool(flag)](when_true, when_false)()


def _unknown_grammar(language):
    """The unknown_grammar fault, returned as data for a grammar this module does not carry.

    The language is a bounded vocabulary — the ten grammars _LANGUAGES holds — so a miss can only be
    a program bug, hence category server. A table miss returns a fault rather than raising, exactly
    as `language_of` does for an unplaceable extension.
    """
    return {
        "err": {
            "code": "unknown_grammar",
            "message": f"no grammar named {language!r}; honest-parse carries {', '.join(sorted(_LANGUAGES))}",
            "category": "server",
            "detail": {"language": language},
        }
    }


def parse(source: bytes, language: str):
    """Parse source bytes under the named grammar: the tree-sitter tree, or an unknown_grammar fault
    for a language the table does not hold."""
    return _pick(
        language in _LANGUAGES,
        lambda: Parser(_LANGUAGES[language]).parse(source),
        lambda: _unknown_grammar(language),
    )












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
    for node in filter(lambda node: node.is_error or node.is_missing, walk(root)):
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
    match = next(filter(lambda item: path.endswith(item[0]), _LANGUAGE_BY_SUFFIX.items()), None)
    return _pick(
        match is None,
        lambda: {
            "err": {
                "code": "unplaceable_extension",
                "message": f"no grammar is declared for the extension of {path!r}; the table carries "
                           f"{', '.join(sorted(_LANGUAGE_BY_SUFFIX))}",
                "category": "client",
                "detail": {"path": path},
            }
        },
        lambda: {"ok": match[1]},
    )


def _syntax_error(root, path: str, language: str):
    """The located syntax_error fault for a tree that already carries a parse error. Pure: it reads
    the already-built tree and touches no world."""
    line, col = line_col(first_error_node(root))
    return {
        "err": {
            "code": "syntax_error",
            "message": f"{path} does not parse under {language}: error at line {line}, column {col}",
            "category": "client",
            "detail": {"path": path, "line": line, "col": col},
        }
    }


def _checked_tree(tree, path: str, language: str):
    """ok(tree) for a clean tree, or the located syntax_error fault. Pure: it reads the already-built
    tree and touches no world."""
    return _pick(
        tree.root_node.has_error,
        lambda: _syntax_error(tree.root_node, path, language),
        lambda: {"ok": tree},
    )


def place_source(source: bytes, path: str):
    """The tree for source read under the grammar its path names: ok(tree), or the chooser's err.

    The module's one orchestrator. It reads the extension through `language_of` and hands the
    language to `parse`, so the choice of grammar happens in one place and the world is touched in
    one other. It holds the routing and nothing else does.
    """
    language = language_of(path)
    return _pick(
        "ok" in language,
        lambda: _checked_tree(parse(source, language["ok"]), path, language["ok"]),
        lambda: language,
    )


def parse_source(source: bytes, path: str):
    """The door: where a calling module arrives, and where its answer goes back.

    Thin, and I/O only. It hands the call to the one orchestrator and adds nothing of its own. This
    module writes nothing anywhere, so its work is consumed by travelling back through here, and a
    function declared as writing to the caller would be a false card: a return is not a write.
    """
    return place_source(source, path)


__all__ = [
    "first_error_node",
    "language_of",
    "line_col",
    "parse",
    "parse_source",
    "place_source",
    "walk",
]
