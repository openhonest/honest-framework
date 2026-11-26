# scenario: parse_root_node preserves recovery nodes for malformed source
# inherits: hd=python/honest-parse/honest-parse.hd::parse_root_node -> feature=specs/features/honest-parse.feature::parse_root_node preserves recovery nodes for malformed source
"""Verify that parse_root_node preserves recovery nodes for malformed source."""


def probe_parse_root_node_recovery():
    try:
        from honest_parse import parse_root_node, walk
    except ImportError as exc:
        return [f"cannot import parse_root_node: {exc}"]

    source = b"def f(:\n"
    got = parse_root_node(source, "python")
    if getattr(got, "type", None) != "module" or any(
        (getattr(got, "text", None) != source, not getattr(got, "has_error", False))
    ):
        return [f"parse_root_node returned {got!r}, expected a recovered Python module root"]
    if not any(node.is_error or node.is_missing for node in walk(got)):
        return ["parse_root_node lost the parser recovery descendants"]
    return []
