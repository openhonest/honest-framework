# scenario: read_root_node returns the fault for an unknown grammar
# inherits: hd=python/honest-parse/honest-parse.hd::read_root_node -> feature=specs/features/honest-parse.feature::read_root_node returns the fault for an unknown grammar
"""Verify that read_root_node returns the fault for an unknown grammar."""


def probe_read_root_node_unknown_grammar():
    try:
        from honest_parse import parse, read_root_node
    except ImportError as exc:
        return [f"cannot import read_root_node: {exc}"]

    source = b"answer = 42\n"
    language = "unknown-grammar"
    expected = parse(source, language)
    got = read_root_node(source, language)
    if got != expected:
        return [f"read_root_node returned {got!r}, expected the parser's unknown_grammar Fault"]
    return []
