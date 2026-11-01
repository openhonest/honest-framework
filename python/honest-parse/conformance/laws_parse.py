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
    parse,
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
        "language": "javascript",
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
        "language": "ruby",
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
        "language": "php",
        "corpus": [
            "<?php\n$x = 1;\n",
            "<?php\nfunction f($a) { return $a + 1; }\n",
            "<?php\nclass C {}\n",
            "",
        ],
        "invalid": ["<?php\nfunction f(", "<?php\n$x = ", "<?php\nclass {", "<?php\nif ("],
    },
    "go": {
        "language": "go",
        "corpus": [
            "package main\n",
            "package main\nfunc f(a int) int {\n\treturn a + 1\n}\n",
            "package main\nvar x = 3\n",
            "",
        ],
        "invalid": ["package main\nfunc f( {", "package", "var = "],
    },
    "elixir": {
        "language": "elixir",
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
        "language": "html",
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
        "language": "jinja",
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
        "language": "css",
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
        "language": "hd",
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


def _law_node_bytes_match_source():
    bad = []
    for src in _CORPUS:
        source = src.encode("utf-8")
        root = parse(source, "python").root_node
        for node in walk(root):
            expected = source[node.start_byte : node.end_byte].decode("utf-8", "replace")
            if node.text.decode("utf-8", "replace") != expected:
                bad.append(f"node bytes != source slice for a {node.type} node in {src!r}")
        if root.text.decode("utf-8", "replace") != src:
            bad.append(f"root bytes do not span the whole source {src!r}")
    return bad


def _law_walk_complete_and_ordered():
    bad = []
    for src in _CORPUS:
        root = parse(src.encode("utf-8"), "python").root_node
        if list(walk(root)) != _reference_preorder(root):
            bad.append(f"walk order/completeness diverges from pre-order for {src!r}")
    return bad


def _law_line_col():
    """line_col is 1-based and reads the node's start point — exercised across several lines."""
    bad = []
    source = "x = 1\nyy = 22\nzzz = 3\n".encode("utf-8")
    root = parse(source, "python").root_node
    if line_col(root) != (1, 1):
        bad.append(f"root line_col {line_col(root)} != (1, 1)")
    expected = {"x": (1, 1), "yy": (2, 1), "zzz": (3, 1)}
    for node in walk(root):
        if node.type == "identifier":
            name = node.text.decode("utf-8", "replace")
            if name in expected and line_col(node) != expected[name]:
                bad.append(f"line_col({name}) = {line_col(node)} != {expected[name]}")
    return bad


def _law_error_detection():
    bad = []
    for src in _CORPUS:
        root = parse(src.encode("utf-8"), "python").root_node
        if (first_error_node(root) is not None) != root.has_error:
            bad.append(f"first_error_node disagrees with has_error on valid {src!r}")
    for src in _INVALID:
        root = parse(src.encode("utf-8"), "python").root_node
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
        first = [n.type for n in walk(parse(source, "python").root_node)]
        second = [n.type for n in walk(parse(source, "python").root_node)]
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
    # A grammar nobody declared is refused by name. A bare KeyError from a dict lookup is the
    # implementation leaking: it says 'klingon' and nothing about what was asked for, what the
    # module carries, or what to do instead. The principles put typed exceptions at the boundary,
    # and this reader is the boundary.
    from honest_parse import UnknownGrammar

    try:
        parse(b"x = 1", "klingon")
        bad.append("an unknown grammar must be refused by name, never guessed")
    except UnknownGrammar as refusal:
        for needed in ("klingon", "python", "no grammar"):
            if needed not in str(refusal):
                bad.append(f"the refusal must say {needed!r}: {refusal}")
    except KeyError:
        bad.append("a bare KeyError names the missing key and nothing a caller can act on")
    return bad


def _law_grammars():
    """Every non-Python target grammar parses through the one reader: the node-text round-trip and
    error detection hold over each language's corpus, and invalid source is detected. honest-check's
    shape rules reach every target language through exactly this one boundary; honest-DOM (Tier 3) is
    the JS reference gated here. There is no per-language wrapper to agree with: ten names for one
    call with a different constant made ten doors out of one reader."""
    bad = []
    for language, grammar in _GRAMMARS.items():
        for src in grammar["corpus"]:
            source = src.encode("utf-8")
            root = parse(source, language).root_node
            for node in walk(root):
                expected = source[node.start_byte : node.end_byte].decode("utf-8", "replace")
                if node.text.decode("utf-8", "replace") != expected:
                    bad.append(f"node bytes != source slice for a {node.type} node in {language} {src!r}")
            if root.text.decode("utf-8", "replace") != src:
                bad.append(f"root bytes do not span the whole {language} source {src!r}")
            if (first_error_node(root) is not None) != root.has_error:
                bad.append(f"first_error_node disagrees with has_error on valid {language} {src!r}")
        for src in grammar["invalid"]:
            if first_error_node(parse(src.encode("utf-8"), language).root_node) is None:
                bad.append(f"no error node found for invalid {language} {src!r}")
    return bad


def _law_utf8_decoding():
    bad = []
    source = "s = 'é日本'".encode("utf-8")  # accented + CJK
    root = parse(source, "python").root_node
    strings = [n.text.decode("utf-8", "replace") for n in walk(root) if n.type == "string"]
    if not strings or "é日本" not in strings[0]:
        bad.append(f"multibyte string literal did not decode: {strings}")
    # Malformed UTF-8 must not crash the decode (the 'replace' path).
    malformed = b"s = '" + b"\xff\xfe" + b"'"
    parse(malformed, "python").root_node.text.decode("utf-8", "replace")
    return bad


def _law_language_of_and_parse_source():
    """The one chooser and the one orchestrator (architecture: the three roles, one of each).

    `language_of` answers which grammar a path is read under, from a table written out in full. An
    extension the table does not carry is a named failure and never a fall-back to the commonest
    grammar: reading a Ruby file under the Python grammar reports a clean parse, so the file passes
    every rule that reads its tree while nothing has actually read the file.

    `parse_source` is the only function here that calls another. It reads the extension through
    `language_of`, hands the language to `parse`, and carries up whichever failure it meets.
    """
    from honest_parse import language_of, parse_source, place_source

    bad = []
    expected = {
        "app.py": "python", "a/b/mod.py": "python",
        "x.js": "javascript", "x.mjs": "javascript", "x.cjs": "javascript",
        "x.rb": "ruby", "x.php": "php", "x.go": "go", "x.ex": "elixir", "x.exs": "elixir",
        "x.html": "html", "x.htm": "html", "x.jinja": "jinja", "x.j2": "jinja",
        "x.css": "css", "x.hd": "hd",
    }
    for path, language in expected.items():
        answer = language_of(path)
        if answer.get("ok") != language:
            bad.append(f"language_of({path!r}) must answer {language!r}: {answer}")

    # Every grammar the module carries must be reachable by extension, or a file of that language
    # can never be read through the orchestrator.
    from honest_parse import _LANGUAGES
    reachable = {language_of(p)["ok"] for p in expected if "ok" in language_of(p)}
    unreachable = sorted(set(_LANGUAGES) - reachable)
    if unreachable:
        bad.append(f"every grammar must be reachable by some extension; these are not: {unreachable}")

    for path in ("x.rs", "x", "x.", "x.PY.txt", ""):
        answer = language_of(path)
        if "err" not in answer:
            bad.append(f"an extension the table does not carry must be a named failure: {path!r} -> {answer}")
        elif "extension" not in answer["err"]["message"]:
            bad.append(f"the failure must say what it could not place: {answer['err']['message']}")

    tree = parse_source(b"x = 1\n", "app.py")
    if "ok" not in tree:
        bad.append(f"parse_source must answer a tree for source it can place: {tree}")
    elif tree["ok"].root_node.has_error:
        bad.append("parse_source read valid Python as broken")
    elif tree["ok"].root_node.text.decode("utf-8", "replace") != "x = 1\n":
        bad.append("parse_source must answer the tree for the whole source it was given")

    # The door is thin: it hands the call to the one orchestrator and adds nothing of its own, so
    # the two answer alike for every input. A door that transformed its answer would be doing work
    # the orchestrator is supposed to hold.
    for source, path in [(b"x = 1\n", "app.py"), (b"x = 1\n", "app.rs"), (b"", "a.css")]:
        through_door = parse_source(source, path)
        through_orchestrator = place_source(source, path)
        if ("ok" in through_door) != ("ok" in through_orchestrator):
            bad.append(f"the door and the orchestrator must agree on {path!r}: "
                       f"{through_door} vs {through_orchestrator}")
        if "err" in through_door and through_door["err"] != through_orchestrator["err"]:
            bad.append(f"the door must hand back the orchestrator's failure unchanged on {path!r}")

    # The orchestrator calls the chooser, so the chooser's failure is the orchestrator's answer.
    refused = parse_source(b"x = 1\n", "app.rs")
    if "err" not in refused:
        bad.append(f"parse_source must carry up the chooser's failure: {refused}")

    # Ruby source placed by its extension is read under the Ruby grammar and not the commonest one.
    ruby = parse_source(b"def f(x)\n  x + 1\nend\n", "lib/a.rb")
    if "ok" not in ruby or ruby["ok"].root_node.has_error:
        bad.append(f"parse_source must read .rb under the Ruby grammar: {ruby}")

    # Source that does not parse is refused with a located fault. The orchestrator finds the error
    # with first_error_node and places it with line_col, so the caller is told where rather than
    # handed a tree it has to scan itself. This is what reconnects those two to the orchestrator.
    broken = parse_source(b"def f(:\n    pass\n", "bad.py")
    if "err" not in broken:
        bad.append(f"source that does not parse must be refused, not handed back as a tree: {broken}")
    elif broken["err"]["code"] != "syntax_error":
        bad.append(f"a parse error is a located syntax_error fault: {broken['err']}")
    elif "line" not in broken["err"]["detail"] or "col" not in broken["err"]["detail"]:
        bad.append(f"the fault carries the line and column of the error: {broken['err']}")
    return bad


def _law_language_vocabulary_is_single_source():
    """The card's Language vocabulary is the one source for the ten grammars.

    The ten grammar names live in three places: the card (`vocabulary Language`, a set of ten
    words), the code (the `_LANGUAGES` table), and this test (`_GRAMMARS` plus python, handled
    inline). Three copies drift. The card is the declaration, so it is the source: the code's table
    and the test's corpus are held to exactly its members, and adding a grammar to one without the
    card, or to the card without the others, fails here.
    """
    from honest_design import read_hd
    from honest_parse import _LANGUAGES

    bad = []
    module = read_hd(open("honest-parse/honest-parse.hd").read())["ok"]["modules"][0]
    sets = {s["name"]: [x["value"] for x in s["members"]] for s in module["sets"]}
    language = next(v for v in module["vocabularies"] if v["name"] == "Language")
    declared = {member for set_name in language["sets"] for member in sets[set_name]}

    if declared != set(_LANGUAGES):
        bad.append(f"the code table and the card's Language vocabulary must be the same ten: "
                   f"card only {sorted(declared - set(_LANGUAGES))}, code only {sorted(set(_LANGUAGES) - declared)}")

    tested = set(_GRAMMARS) | {"python"}
    if tested != declared:
        bad.append(f"every grammar the card declares must have a test corpus: "
                   f"card only {sorted(declared - tested)}, test only {sorted(tested - declared)}")
    return bad


def _law_fault_details_and_surface():
    """The fault details and the public surface are pinned, not only the happy path. A mutant that
    blanks a fault code, category, message or detail, swaps a fault key, or drops an export survives a
    suite that proves parsing behaviour alone; these assertions catch them."""
    import honest_parse
    from honest_parse import _LANGUAGE_BY_SUFFIX, _LANGUAGES, UnknownGrammar, language_of, parse, place_source

    bad = []

    expected_all = ["UnknownGrammar", "first_error_node", "language_of", "line_col", "parse", "parse_source", "place_source", "walk"]
    if honest_parse.__all__ != expected_all:
        bad.append(f"__all__ drifted from the declared surface: {honest_parse.__all__}")

    unplaceable = language_of("a.rs")
    if "err" not in unplaceable:
        bad.append(f"an unplaceable extension must be a fault: {unplaceable}")
    else:
        e = unplaceable["err"]
        if e.get("code") != "unplaceable_extension":
            bad.append(f"the unplaceable fault code must be 'unplaceable_extension': {e.get('code')!r}")
        if e.get("category") != "client":
            bad.append(f"the unplaceable fault category must be 'client': {e.get('category')!r}")
        if e.get("detail") != {"path": "a.rs"}:
            bad.append(f"the unplaceable fault detail must carry the path: {e.get('detail')}")
        if "a.rs" not in e.get("message", "") or ", ".join(sorted(_LANGUAGE_BY_SUFFIX)) not in e.get("message", ""):
            bad.append(f"the unplaceable fault message must name the path and the separated list of known extensions: {e.get('message')}")

    broken = place_source(b"def f(:\n", "bad.py")
    if "err" not in broken:
        bad.append(f"source that does not parse must be a fault: {broken}")
    else:
        e = broken["err"]
        if e.get("code") != "syntax_error":
            bad.append(f"the syntax fault code must be 'syntax_error': {e.get('code')!r}")
        if e.get("category") != "client":
            bad.append(f"the syntax fault category must be 'client': {e.get('category')!r}")
        detail = e.get("detail", {})
        if detail.get("path") != "bad.py" or "line" not in detail or "col" not in detail:
            bad.append(f"the syntax fault detail must carry path, line and col: {detail}")
        if "bad.py" not in e.get("message", "") or "line" not in e.get("message", "") or "column" not in e.get("message", ""):
            bad.append(f"the syntax fault message must name the file, line and column: {e.get('message')}")

    try:
        parse(b"x = 1\n", "nope")
        bad.append("parse must raise UnknownGrammar for an unknown grammar")
    except UnknownGrammar as exc:
        if "nope" not in str(exc) or ", ".join(sorted(_LANGUAGES)) not in str(exc):
            bad.append(f"the UnknownGrammar message must name the grammar and the separated registry: {exc}")

    return bad


_LAWS = {
    "node_bytes_match_source": _law_node_bytes_match_source,
    "fault_details_and_surface": _law_fault_details_and_surface,
    "walk_complete_ordered": _law_walk_complete_and_ordered,
    "line_col": _law_line_col,
    "error_detection": _law_error_detection,
    "determinism": _law_determinism,
    "language_vocabulary": _law_language_vocabulary,
    "language_vocabulary_is_single_source": _law_language_vocabulary_is_single_source,
    "language_of_and_parse_source": _law_language_of_and_parse_source,
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
