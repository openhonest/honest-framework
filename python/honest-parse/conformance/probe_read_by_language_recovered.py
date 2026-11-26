# scenario: read_by_language returns the original recovered tree
# inherits: hd=python/honest-parse/honest-parse.hd::read_by_language -> feature=specs/features/honest-parse.feature::read_by_language returns the original recovered tree
"""Verify that read_by_language returns the original recovered tree."""


def probe_read_by_language_recovered():
    try:
        from honest_parse import read_by_language, walk
    except ImportError as exc:
        return [f"cannot import read_by_language: {exc}"]

    source = b"value = 1\ndef f(:\n"
    tree = read_by_language(source, "python")
    root = getattr(tree, "root_node", None)
    if root is None or (root.type, root.text) != ("module", source):
        return [f"read_by_language returned {tree!r}, expected the Python tree"]
    if not any(node.is_error or node.is_missing for node in walk(root)):
        return ["read_by_language dropped the parser recovery nodes"]
    return []
