# scenario: read_tree parses the bytes using the resolved grammar
# inherits: hd=python/honest-parse/honest-parse.hd::read_tree -> feature=specs/features/honest-parse.feature::read_tree parses the bytes using the resolved grammar
"""Verify that read_tree parses the bytes using the resolved grammar."""


def probe_read_tree_python():
    try:
        from honest_parse import _LANGUAGES, read_tree
    except ImportError as exc:
        return [f"cannot import read_tree: {exc}"]

    source = b"value = 1\n"
    tree = read_tree(source, _LANGUAGES["python"])
    root = getattr(tree, "root_node", None)
    expected = ("module", source, False)
    if root is None or (root.type, root.text, root.has_error) != expected:
        return [f"read_tree returned {tree!r}, expected the Python tree"]
    if read_tree(source, _LANGUAGES["python"]) is tree:
        return ["read_tree reused the prior Tree instead of making a fresh parse"]
    return []
