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

from honest_parse import first_error_node, line_col, node_text, parse, parse_python, walk

_CORPUS = [
    "x = 1",
    "def f(a, b):\n    return a + b\n",
    "class C(Base):\n    pass\n",
    "y = 'hello'\nz = [1, 2, 3]\n",
    "if a == 1:\n    b = 2\nelse:\n    b = 3\n",
    "",
]

_INVALID = ["def f(:", "x = 'abc", "(", "return = "]


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
    """A known language parses; an unknown one is rejected, never guessed (closed vocabulary)."""
    bad = []
    if parse(b"x = 1", "python").root_node.has_error:
        bad.append("parse(.., 'python') failed on valid source")
    try:
        parse(b"x = 1", "klingon")
        bad.append("an unknown language should raise KeyError, not be guessed")
    except KeyError:
        pass
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
