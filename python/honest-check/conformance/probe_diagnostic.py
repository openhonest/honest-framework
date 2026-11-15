"""Honest probe for honest-check's diagnostic (feature Scenario: diagnostic).

diagnostic is the one pure builder every rule calls to assemble a finding. It
fills rule_id, severity and message straight from its arguments; derives
source_location as `path:line:col` where path comes from the CheckContext and
line and col come from the node's byte span over the context's source bytes
(1-based, matching honest-parse's line_col and the spec's `report.py:67:1`
example); quotes context verbatim from that source line; and sets fixable from
whether rule_id sits in honest-check's conservative auto-fix subset.

The cases parse one real Python snippet with honest-parse, pick real nodes by
type (never fabricated), and pin literal expected values: an `if_statement` at
line 2 column 1 and a `string` at line 2 column 12, both quoting the same
source line. A stub `return {"rule_id": "", "severity": "", "message": "",
"source_location": "", "context": "", "fixable": False}` fails every
pass-through and both source_location/context cases, so the probe is not
vacuous.

Gap: the .hd and scenario never enumerate the conservative auto-fix subset, so
fixable's membership is not fixed. The probe asserts only that fixable is a
bool and reports the subset as a gap rather than inventing membership.
"""
from honest_parse import parse, walk

# One real snippet, parsed once. Line 2 is `if role == "admin":`.
_SOURCE = b'x = 1\nif role == "admin":\n    pass\n'
_PATH = "src/demo.py"

# Each case: the finding's rule_id/severity/message, the real node to locate it
# (picked by tree-sitter node type), and the exact source_location and context
# diagnostic must produce for that node over _SOURCE at _PATH.
_CASES = [
    {
        "rule_id": "HC-P001",
        "severity": "error",
        "message": "if/elif/else discriminant dispatch",
        "node_type": "if_statement",
        "source_location": "src/demo.py:2:1",
        "context": 'if role == "admin":',
    },
    {
        "rule_id": "HC001",
        "severity": "warning",
        "message": "recognizer names a literal",
        "node_type": "string",
        "source_location": "src/demo.py:2:12",
        "context": 'if role == "admin":',
    },
]


def _pick_node(root, node_type):
    for node in walk(root):
        if node.type == node_type:
            return node
    return None


def probe_diagnostic():
    """diagnostic builds one Diagnostic: args pass through, source_location is
    path:line:col for the node, context is the verbatim source line."""
    try:
        from honest_check import diagnostic
    except ImportError as exc:
        return [f"cannot import diagnostic: {exc}"]

    tree = parse(_SOURCE, "python")
    root = tree.root_node
    ctx = {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": _SOURCE,
        "path": _PATH,
        "rule_config": {},
    }

    bad = []
    for case in _CASES:
        node = _pick_node(root, case["node_type"])
        if node is None:
            bad.append(f"no {case['node_type']} node in the parsed snippet")
            continue
        got = diagnostic(
            ctx=ctx,
            rule_id=case["rule_id"],
            severity=case["severity"],
            message=case["message"],
            node=node,
        )
        for field in ("rule_id", "severity", "message", "source_location", "context"):
            if got[field] != case[field]:
                bad.append(
                    f"diagnostic({case['rule_id']}, node={case['node_type']})"
                    f"[{field}] -> {got[field]!r}, expected {case[field]!r}"
                )
        # The auto-fix subset is not enumerated in the .hd or scenario, so its
        # membership is a gap; only fixable's type is fixed.
        if not isinstance(got["fixable"], bool):
            bad.append(
                f"diagnostic({case['rule_id']})[fixable] -> {got['fixable']!r}, "
                f"expected a bool"
            )
    return bad
