# scenario: parse_root_node returns the unknown grammar fault
# inherits: hd=python/honest-parse/honest-parse.hd::parse_root_node -> feature=specs/features/honest-parse.feature::parse_root_node returns the unknown grammar fault
"""Verify that parse_root_node returns the unknown grammar fault."""


def probe_parse_root_node_unknown_grammar():
    try:
        from honest_parse import parse, parse_root_node
    except ImportError as exc:
        return [f"cannot import parse_root_node: {exc}"]

    source = b"answer = 42\n"
    language = "unknown-grammar"
    expected = parse(source, language)
    got = parse_root_node(source, language)
    if got != expected:
        return [f"parse_root_node returned {got!r}, expected the parser's unknown_grammar Fault"]
    return []
