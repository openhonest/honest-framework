# scenario: root_node_or_fault returns the actual tree root
# inherits: hd=python/honest-parse/honest-parse.hd::root_node_or_fault -> feature=specs/features/honest-parse.feature::root_node_or_fault returns the actual tree root
"""Verify that root_node_or_fault returns the actual tree root."""


def probe_root_node_or_fault_tree():
    try:
        from honest_parse import parse, root_node_or_fault
    except ImportError as exc:
        return [f"cannot import root_node_or_fault: {exc}"]

    tree = parse(b"answer = 42\n", "python")
    got = root_node_or_fault(tree)
    if got != tree.root_node:
        return [f"root_node_or_fault returned {got!r}, expected the same tree's root"]
    return []
