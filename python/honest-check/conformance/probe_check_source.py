"""Honest probe for honest-check's check_source (feature Scenario: check_source).

check_source is the pure rule-running core. Given an already-built CheckContext
and the module's declaration (or NOTHING in base mode), it runs every rule in the
RuleId catalogue over the context by threading it through check_construction and
check_per_file and then apply_suppression, and returns the findings as data — a
list of Diagnostic, empty when the source is clean. It opens no file, executes
none of the code it inspects, parses nothing itself, and raises nothing.

build_context is also absent in the clean-slate rebuild, so each case builds a
real CheckContext directly from a live honest-parse parse, per the CheckContext
record the .hd declares (root, nodes, aliases, roles, source, path, rule_config).
The violation case holds one `if` statement, which HC-P001 forbids (any `if` but
the `if __name__ == "__main__"` guard), and pins the exact diagnostic: rule_id
HC-P001, severity error, line 2 — the line the `if` sits on. The clean case holds
no `if` and must yield no finding, the explicit empty-list case. declaration is
NOTHING (None) for base mode. The diagnostics are exact-matched, so a false
positive — any extra finding — fails too. A stub `return []` passes the clean case
but fails the violation case, which demands exactly one HC-P001 error at line 2.
"""
import honest_parse

# NOTHING, the absence arm of the declaration parameter: None in this
# implementation, so check_source runs in base mode and crosses no .hd.
NOTHING = None


def _context(source, path):
    """A real CheckContext over source, built from a live honest-parse parse.

    The parsed tree is returned alongside so the caller holds it while the nodes
    are read (the nodes point back into the live tree).
    """
    tree = honest_parse.parse_source(source, path)["ok"]
    root = tree.root_node
    context = {
        "root": root,
        "nodes": honest_parse.walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": path,
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }
    return tree, context


# A function body carrying one `if` (the HC-P001 violation, on line 2) and a clean
# function carrying none.
_VIOLATION = b"def f(x):\n    if x:\n        return 1\n    return 0\n"
_CLEAN = b"def g(x):\n    return x\n"

# Each case: the source a context is built over, and the (rule_id, severity, line)
# of every Diagnostic check_source must return, in order.
_CASES = [
    {"source": _VIOLATION, "path": "mod.py", "expect": [("HC-P001", "error", 2)]},
    {"source": _CLEAN, "path": "clean.py", "expect": []},
]


def _line_of(source_location):
    """The line number out of a 'file:line:col' source_location."""
    return int(source_location.split(":")[1])


def probe_check_source():
    """check_source returns exactly one HC-P001 error at the `if`'s line, and nothing for a clean source."""
    try:
        from honest_check import check_source
    except ImportError as exc:
        return [f"cannot import check_source: {exc}"]

    bad = []
    for case in _CASES:
        tree, context = _context(case["source"], case["path"])
        diagnostics = check_source(context=context, declaration=NOTHING)
        got = [
            (d["rule_id"], d["severity"], _line_of(d["source_location"]))
            for d in diagnostics
        ]
        if got != case["expect"]:
            bad.append(
                f"check_source({case['source']!r}) -> {got}, expected {case['expect']}"
            )
        # Hold the tree until after the call so the nodes stay valid.
        tree.root_node
    return bad
