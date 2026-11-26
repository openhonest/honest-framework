# scenario: read_root_node returns the recovered root for the requested grammar
# inherits: hd=python/honest-parse/honest-parse.hd::read_root_node -> feature=specs/features/honest-parse.feature::read_root_node returns the recovered root for the requested grammar
"""Verify that read_root_node returns the recovered root for the requested grammar."""


def probe_read_root_node_recovery():
    try:
        from honest_parse import parse, read_root_node, walk
    except ImportError as exc:
        return [f"cannot import read_root_node: {exc}"]

    source = b"def f(:\n"
    language = "python"
    expected = parse(source, language).root_node
    got = read_root_node(source, language)
    if getattr(got, "type", None) != expected.type or getattr(got, "text", None) != source:
        return [f"read_root_node returned {got!r}, expected the Python module root over {source!r}"]
    signature = [
        (node.type, node.start_byte, node.end_byte, node.is_error, node.is_missing)
        for node in walk(got)
    ]
    expected_signature = [
        (node.type, node.start_byte, node.end_byte, node.is_error, node.is_missing)
        for node in walk(expected)
    ]
    if signature != expected_signature or not any(row[3] or row[4] for row in signature):
        return [f"read_root_node returned recovery shape {signature!r}, expected {expected_signature!r}"]
    return []
