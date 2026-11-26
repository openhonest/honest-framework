# scenario: root_node_or_fault passes through the unknown grammar fault
# inherits: hd=python/honest-parse/honest-parse.hd::root_node_or_fault -> feature=specs/features/honest-parse.feature::root_node_or_fault passes through the unknown grammar fault
"""Verify that root_node_or_fault passes through the unknown grammar fault."""


def probe_root_node_or_fault_fault():
    try:
        from honest_parse import parse, root_node_or_fault
    except ImportError as exc:
        return [f"cannot import root_node_or_fault: {exc}"]

    fault = parse(b"answer = 42\n", "unknown-grammar")
    got = root_node_or_fault(fault)
    if got is not fault:
        return [f"root_node_or_fault returned {got!r}, expected the identical unknown_grammar Fault"]
    return []
