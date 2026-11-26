# scenario: parse_root_node returns the root for the explicit grammar
# inherits: hd=python/honest-parse/honest-parse.hd::parse_root_node -> feature=specs/features/honest-parse.feature::parse_root_node returns the root for the explicit grammar
"""Verify that parse_root_node returns the root for the explicit grammar."""


def probe_parse_root_node_explicit_grammar():
    try:
        from honest_parse import parse_root_node
    except ImportError as exc:
        return [f"cannot import parse_root_node: {exc}"]

    source = b"answer = 42\n"
    got = parse_root_node(source, "python")
    if (getattr(got, "type", None), getattr(got, "text", None), getattr(got, "has_error", None)) != ("module", source, False):
        return [f"parse_root_node returned {got!r}, expected a clean Python module root"]
    return []
