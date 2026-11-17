"""RED probe for honest-test.parse_source — the tree-sitter parse (.hd, sections 2, 9.6).

parse_source parses one source file's text with tree-sitter and returns the tree's
root node. The parse is deterministic and reads no world; tree-sitter produces a
tree with error nodes for malformed input rather than failing, so parse_source
returns a node, never a fault, even on broken source. honest-test has no code yet,
so importing honest_test fails — the correct red state.
"""

from honest_test import parse_source


def _is_fault(value):
    """honest-test's own Fault carries problem and remedy (.hd Fault type)."""
    return isinstance(value, dict) and "problem" in value and "remedy" in value


def _is_node(value):
    """A tree-sitter node carries a type and children; a root node, nothing else."""
    return value is not None and hasattr(value, "type") and hasattr(value, "children")


def probe_parse_source():
    """parse_source returns the tree-sitter root node for valid source and still
    returns a node — never a fault, never an exception — for malformed source."""
    bad = []

    valid = "def recognize(s):\n    return len(s) == 5\n"
    root = parse_source(valid)
    if _is_fault(root):
        bad.append(f"parse_source returned a fault on valid source: {root!r}")
    elif not _is_node(root):
        bad.append(f"parse_source returned {root!r}, expected a tree-sitter root node")
    elif root.type != "module":
        bad.append(f"the python root node type is {root.type!r}, expected 'module'")

    # Malformed source: tree-sitter builds error nodes, so parse_source still
    # returns a node and raises nothing.
    malformed = "def recognize(s:\n    return len(s ==\n"
    try:
        broken = parse_source(malformed)
    except Exception as e:  # noqa: BLE001 — the probe records, it does not re-raise
        bad.append(f"parse_source raised on malformed source instead of returning a node: {e!r}")
    else:
        if _is_fault(broken):
            bad.append(f"parse_source returned a fault on malformed source, expected a node: {broken!r}")
        elif not _is_node(broken):
            bad.append(f"parse_source returned {broken!r} on malformed source, expected a node")

    return bad


def run():
    failures = probe_parse_source()
    for message in failures:
        print(f"FAIL parse_source: {message}")
    print(f"parse_source probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
