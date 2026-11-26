# scenario: root_node_or_fault preserves recovery descendants
# inherits: hd=python/honest-parse/honest-parse.hd::root_node_or_fault -> feature=specs/features/honest-parse.feature::root_node_or_fault preserves recovery descendants
"""Verify that root_node_or_fault preserves recovery descendants."""


def probe_root_node_or_fault_recovery():
    try:
        from honest_parse import parse, root_node_or_fault, walk
    except ImportError as exc:
        return [f"cannot import root_node_or_fault: {exc}"]

    tree = parse(b"def f(:\n", "python")
    got = root_node_or_fault(tree)
    if got != tree.root_node or not any(node.is_error or node.is_missing for node in walk(got)):
        return [f"root_node_or_fault returned {got!r}, expected the same tree's recovered root"]
    return []
