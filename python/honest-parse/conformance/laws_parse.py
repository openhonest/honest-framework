"""honest-parse conformance: parser-boundary laws (the generative circle).

honest-parse is the framework's single tree-sitter boundary. Its behaviour is a set of
universal properties over ANY parsed source, not a fixed list of examples:

  - node-text round-trip: every node's text is exactly the source slice it spans;
  - walk: yields every node once, depth-first, parents before children;
  - line/col: 1-based, derived from the node's start point;
  - error detection: first_error_node is non-None iff the tree carries an error;
  - determinism: the same source parses to the same structure every time;
  - closed language vocabulary: a known language parses, an unknown one is rejected
    (KeyError), never guessed;
  - UTF-8 decoding: multibyte text decodes correctly and malformed bytes do not crash.

Each law is asserted over a corpus of snippets — exhaustive over every node each produces.
honest-parse is the base layer (honest-check and honest-test depend on it), so its
conformance depends only on honest_parse itself: no upward import of honest-test's runner.
The conformance directory is outside the honest-check gate, so this file is free to drive
malformed bytes and unknown languages on purpose.
"""

from honest_parse import (
    first_error_node,
    line_col,
    node_text,
    parse,
    parse_elixir,
    parse_css,
    parse_go,
    parse_hd,
    parse_html,
    parse_jinja,
    parse_javascript,
    parse_php,
    parse_python,
    parse_ruby,
    walk,
)

_CORPUS = [
    "x = 1",
    "def f(a, b):\n    return a + b\n",
    "class C(Base):\n    pass\n",
    "y = 'hello'\nz = [1, 2, 3]\n",
    "if a == 1:\n    b = 2\nelse:\n    b = 3\n",
    "",
]

_INVALID = ["def f(:", "x = 'abc", "(", "return = "]

# Every non-Python grammar is checked uniformly through the shared boundary (node-text round-trip,
# error detection on valid and invalid source, and wrapper/`parse` agreement) over a per-language
# corpus. Python is the deep reference language exercised by the laws above; each other framework
# target grammar earns its row here. This is data, not branches: adding a language extends the table.
_GRAMMARS = {
    "javascript": {
        "parse": parse_javascript,
        "corpus": [
            "const x = 1;",
            "function f(a, b) {\n    return a + b;\n}\n",
            "let y = 'hello';\nconst z = [1, 2, 3];\n",
            "if (a === 1) {\n    b = 2;\n} else {\n    b = 3;\n}\n",
            "",
        ],
        "invalid": ["function f(", "const x = 'abc", "{", "let = "],
    },
    "ruby": {
        "parse": parse_ruby,
        "corpus": [
            "x = 1\n",
            "def f(a, b)\n  a + b\nend\n",
            "class C < Base\nend\n",
            "[1, 2, 3].each { |n| p n }\n",
            "",
        ],
        "invalid": ["def f(", "x = [1, 2", "class ", "if a"],
    },
    "php": {
        "parse": parse_php,
        "corpus": [
            "<?php\n$x = 1;\n",
            "<?php\nfunction f($a) { return $a + 1; }\n",
            "<?php\nclass C {}\n",
            "",
        ],
        "invalid": ["<?php\nfunction f(", "<?php\n$x = ", "<?php\nclass {", "<?php\nif ("],
    },
    "go": {
        "parse": parse_go,
        "corpus": [
            "package main\n",
            "package main\nfunc f(a int) int {\n\treturn a + 1\n}\n",
            "package main\nvar x = 3\n",
            "",
        ],
        "invalid": ["package main\nfunc f( {", "package", "var = "],
    },
    "elixir": {
        "parse": parse_elixir,
        "corpus": [
            "x = 1\n",
            "defmodule M do\n  def f(x), do: x + 1\nend\n",
            "[1, 2, 3]\n",
            "",
        ],
        "invalid": ["defmodule do", "def f(", "[1, 2"],
    },
    # HTML/HTMX templates: the single parser reads them so the input boundary stays inspectable
    # (framework spec, "The input boundary is closed"). The corpus carries the attributes HC002's
    # boundary-vocabulary derivation reads — hx-post/hx-get targets, form field names, hx-vals keys,
    # dx-manifest. HTML is error-tolerant of mismatched tags, so the invalid set uses genuinely
    # malformed syntax (unclosed tag, missing attribute value, unterminated string, garbage).
    "html": {
        "parse": parse_html,
        "corpus": [
            '<button hx-post="/api/orders" hx-vals=\'{"qty": 3}\'>Buy</button>\n',
            '<form hx-post="/api/orders"><input name="qty"><input name="sku"></form>\n',
            '<body dx-manifest="appManifest"></body>\n',
            "<div></div>\n",
            "",
        ],
        "invalid": ["<button hx-post=>", "<form", "<<<", '<a href=">'],
    },
    # Jinja templates: honest-parse's own template grammar, surfacing {% include %}/{% extends %} targets
    # the HTML grammar cannot (it reads Jinja tags as opaque text). The grammar is deliberately
    # error-tolerant of tag interiors and HTML, so the corpus mixes extends/include (literal and dynamic),
    # blocks, output, comments, and HTML; the invalid set is genuinely malformed — an unclosed statement,
    # output, or comment, and an unterminated string — each of which the grammar cannot complete.
    "jinja": {
        "parse": parse_jinja,
        "corpus": [
            '{% extends "base.html" %}\n',
            '{% block main %}{% include "molecules/card/card.html" %}{% endblock %}\n',
            '{% include some_var %}{{ user.name }}{# note #}\n',
            '<div class="x" hx-get="/y">text</div>\n',
            "",
        ],
        "invalid": ['{% include "x"', "{{ y", "{# c", '{% include "x %}'],
    },
    # CSS: the official grammar reads component stylesheets so honest-check can resolve a class reference
    # against the rules a stylesheet defines (HC-REF003). The corpus carries BEM class selectors, custom
    # properties, pseudo-classes, and media queries; the invalid set is genuinely malformed — an
    # unterminated declaration, an unclosed rule, a stray close brace, an empty declaration.
    "css": {
        "parse": parse_css,
        "corpus": [
            ".button { color: var(--ht-color-accent); }\n",
            ".button__text { font-weight: 600; }\n.button--primary:hover { background: red; }\n",
            ":root { --ht-space-md: 1rem; }\n@media (min-width: 700px) { .data-table .row { margin: 0; } }\n",
            "",
        ],
        "invalid": [".button { color: ", ".a {", "} garbage {", ".x { : ; }"],
    },
    # .hd architecture declarations: honest-parse's own grammar, the read path honest-design folds
    # into the IR. The corpus exercises both file kinds and every primitive — module/layer, records
    # and union types, sets with descriptions, vocabularies, dispatch, examples, the four function
    # roles with signatures/side_effects (reads/writes/reads_writes)/invokes/raises (bare and
    # quoted), chains, routes, entry points, html_attr, and the workspace rule/actor/flow files. The
    # invalid set is genuinely malformed — a nameless module, a valueless type, an empty chain, an
    # unterminated string.
    "hd": {
        "parse": parse_hd,
        "corpus": [
            "module m\n  layer foundation\n  type T = { a: str\n b: dict<str, set<str>> }\n"
            "  set s = { \"x\" : \"an x\", \"y\" }\n  vocabulary v = { s }\n"
            "  dispatch d = { \"k\" -> h }\n  example e of c = \"does a thing\"\n"
            "  boundary_in fn read_it : (r: Request) -> list<str> side_effect reads \"HTTP\"\n"
            "  orchestrator fn run : (t: list<str>) -> T invokes c, classify raises bad_input\n"
            "  fn classify : (t: str) -> T | Fault\n"
            "  boundary_out fn write_it : (t: T) -> Response raises \"io.failed\" side_effect reads_writes \"database\"\n"
            "  chain c = classify -> write_it\n  route \"POST /x\" -> read_it\n"
            "  entry \"decorator:@handle\" -> run\n  html_attr \"hx-go\" \"navigate\"\n",
            "rule HC001 = \"Every chain link references a declared function.\"\n"
            "rule HC-R001 on m = \"Every role is reachable.\"\n",
            "actor browser\nflow f in server = browser -> m -> other\n",
            "",
        ],
        "invalid": ["module", "type T =", "chain c =", 'set s = { "a'],
    },
}


def _reference_preorder(node):
    """An independent depth-first, parents-before-children traversal to check walk against."""
    out = [node]
    for child in node.children:
        out.extend(_reference_preorder(child))
    return out


def _law_node_text_roundtrip():
    bad = []
    for src in _CORPUS:
        source = src.encode("utf-8")
        root = parse_python(source).root_node
        for node in walk(root):
            expected = source[node.start_byte : node.end_byte].decode("utf-8", "replace")
            if node_text(node, source) != expected:
                bad.append(f"node_text != source slice for a {node.type} node in {src!r}")
        if node_text(root, source) != src:
            bad.append(f"root node_text does not span the whole source {src!r}")
    return bad


def _law_walk_complete_and_ordered():
    bad = []
    for src in _CORPUS:
        root = parse_python(src.encode("utf-8")).root_node
        if list(walk(root)) != _reference_preorder(root):
            bad.append(f"walk order/completeness diverges from pre-order for {src!r}")
    return bad


def _law_line_col():
    """line_col is 1-based and reads the node's start point — exercised across several lines."""
    bad = []
    source = "x = 1\nyy = 22\nzzz = 3\n".encode("utf-8")
    root = parse_python(source).root_node
    if line_col(root) != (1, 1):
        bad.append(f"root line_col {line_col(root)} != (1, 1)")
    expected = {"x": (1, 1), "yy": (2, 1), "zzz": (3, 1)}
    for node in walk(root):
        if node.type == "identifier":
            name = node_text(node, source)
            if name in expected and line_col(node) != expected[name]:
                bad.append(f"line_col({name}) = {line_col(node)} != {expected[name]}")
    return bad


def _law_error_detection():
    bad = []
    for src in _CORPUS:
        root = parse_python(src.encode("utf-8")).root_node
        if (first_error_node(root) is not None) != root.has_error:
            bad.append(f"first_error_node disagrees with has_error on valid {src!r}")
    for src in _INVALID:
        root = parse_python(src.encode("utf-8")).root_node
        node = first_error_node(root)
        if node is None:
            bad.append(f"no error node found for invalid {src!r}")
        elif not (node.is_error or node.is_missing):
            bad.append(f"first_error_node returned a non-error node for {src!r}")
    return bad


def _law_determinism():
    bad = []
    for src in _CORPUS:
        source = src.encode("utf-8")
        first = [n.type for n in walk(parse_python(source).root_node)]
        second = [n.type for n in walk(parse_python(source).root_node)]
        if first != second:
            bad.append(f"parse is not deterministic for {src!r}")
    return bad


def _law_language_vocabulary():
    """Every known language parses a valid snippet; an unknown one is rejected, never guessed
    (closed vocabulary). All six framework target languages are exercised through the boundary."""
    bad = []
    if parse(b"x = 1", "python").root_node.has_error:
        bad.append("parse(.., 'python') failed on valid source")
    for language, grammar in _GRAMMARS.items():
        if parse(grammar["corpus"][0].encode("utf-8"), language).root_node.has_error:
            bad.append(f"parse(.., {language!r}) failed on valid source")
    try:
        parse(b"x = 1", "klingon")
        bad.append("an unknown language should raise KeyError, not be guessed")
    except KeyError:
        pass
    return bad


def _law_grammars():
    """Every non-Python target grammar parses through the shared boundary: node-text round-trip and
    error detection hold over each language's corpus, invalid source is detected, and the per-language
    convenience wrapper agrees with parse(.., language). honest-check's shape rules reach every target
    language through exactly this one boundary; honest-DOM (Tier 3) is the JS reference gated here."""
    bad = []
    for language, grammar in _GRAMMARS.items():
        parse_lang = grammar["parse"]
        for src in grammar["corpus"]:
            source = src.encode("utf-8")
            root = parse_lang(source).root_node
            for node in walk(root):
                expected = source[node.start_byte : node.end_byte].decode("utf-8", "replace")
                if node_text(node, source) != expected:
                    bad.append(f"node_text != source slice for a {node.type} node in {language} {src!r}")
            if node_text(root, source) != src:
                bad.append(f"root node_text does not span the whole {language} source {src!r}")
            if (first_error_node(root) is not None) != root.has_error:
                bad.append(f"first_error_node disagrees with has_error on valid {language} {src!r}")
        for src in grammar["invalid"]:
            if first_error_node(parse_lang(src.encode("utf-8")).root_node) is None:
                bad.append(f"no error node found for invalid {language} {src!r}")
        first_valid = grammar["corpus"][0].encode("utf-8")
        direct = [n.type for n in walk(parse(first_valid, language).root_node)]
        wrapped = [n.type for n in walk(parse_lang(first_valid).root_node)]
        if direct != wrapped:
            bad.append(f"parse_{language} disagrees with parse(.., {language!r})")
    return bad


def _law_utf8_decoding():
    bad = []
    source = "s = 'é日本'".encode("utf-8")  # accented + CJK
    root = parse_python(source).root_node
    strings = [node_text(n, source) for n in walk(root) if n.type == "string"]
    if not strings or "é日本" not in strings[0]:
        bad.append(f"multibyte string literal did not decode: {strings}")
    # Malformed UTF-8 must not crash node_text (the 'replace' path).
    malformed = b"s = '" + b"\xff\xfe" + b"'"
    node_text(parse_python(malformed).root_node, malformed)
    return bad


_LAWS = {
    "node_text_roundtrip": _law_node_text_roundtrip,
    "walk_complete_ordered": _law_walk_complete_and_ordered,
    "line_col": _law_line_col,
    "error_detection": _law_error_detection,
    "determinism": _law_determinism,
    "language_vocabulary": _law_language_vocabulary,
    "grammars": _law_grammars,
    "utf8_decoding": _law_utf8_decoding,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL parse-law [{name}]: {msgs}")
    print(f"parse laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(run())
