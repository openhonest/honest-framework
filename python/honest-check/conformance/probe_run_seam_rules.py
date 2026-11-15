"""Honest probe for honest-check's run_seam_rules (feature Scenario: run_seam_rules).

run_seam_rules is the orchestrator the seam door hands its inputs to. For each
module named in in_scope (or every loaded module when in_scope is empty) it runs
check_hc_ref006, check_hc_ref007 and check_ref012 over that module's declaration,
the whole declarations map and the module's .hd path, handing check_ref012 the
module's manifest_deps entry (the empty list when absent) and the workspace module
names, concatenating their diagnostics in that order across every in-scope module.
It resolves each in-scope module's seams against the complete declarations map,
not the in-scope subset.

Three cases pin the behaviour:
  - A caller with two seams into one target: a dead door (ghost -> HC-REF006) and a
    wrong-role door (plain, a `fn` -> HC-REF007), pinned in 006-before-007 order.
  - A caller whose seam resolves to a boundary_in door, no manifest coupling -> [].
  - A caller whose seam resolves cleanly but whose manifest depends on another
    workspace module it names no seam onto -> one HC-REF012 error folded in.
A stub `return []` passes the two absence paths and fails both firing cases, so
each ordered non-empty result is a literal no empty body produces.

Inputs are real Declarations parsed by honest-design's read_hd.
"""

# One caller, two seams into target: ghost (no such fn) and plain (role fn).
_SRC_CALLER_TWO = (
    "module caller\n\n"
    '  fn c : (x: str) -> str'
    ' side_effect reads "target.ghost"'
    ' side_effect reads "target.plain"\n'
)
# One caller, one seam into target.good, which target declares as boundary_in.
_SRC_CALLER_GOOD = (
    "module caller\n\n"
    '  fn c : (x: str) -> str side_effect reads "target.good"\n'
)
_SRC_TARGET_PLAIN = (
    "module target\n\n"
    "  fn plain : (x: str) -> str\n"
)
_SRC_TARGET_GOOD = (
    "module target\n\n"
    "  boundary_in fn good : (x: str) -> str\n"
)
# A loaded workspace module caller depends on in its manifest but names no seam onto.
_SRC_OTHER = (
    "module other\n\n"
    "  fn helper : (x: str) -> str\n"
)

# Each case: the .hd sources to load, the manifest_deps map, the in_scope list, and
# the ordered (rule_id, severity) pairs run_seam_rules must return.
_CASES = [
    # Two seams into target: a dead door and a wrong-role door.
    {
        "modules": [_SRC_CALLER_TWO, _SRC_TARGET_PLAIN],
        "manifest_deps": {},
        "in_scope": ["caller"],
        "expect": [("HC-REF006", "error"), ("HC-REF007", "error")],
    },
    # Absence: the seam resolves to a boundary_in door and there is no manifest coupling.
    {
        "modules": [_SRC_CALLER_GOOD, _SRC_TARGET_GOOD],
        "manifest_deps": {},
        "in_scope": ["caller"],
        "expect": [],
    },
    # The seam resolves cleanly, but caller's manifest depends on workspace module
    # `other` it names no seam onto: HC-REF012 folded in after the clean 006/007 pass.
    {
        "modules": [_SRC_CALLER_GOOD, _SRC_TARGET_GOOD, _SRC_OTHER],
        "manifest_deps": {"caller": ["other"]},
        "in_scope": ["caller"],
        "expect": [("HC-REF012", "error")],
    },
]


def probe_run_seam_rules():
    """run_seam_rules folds HC-REF006, HC-REF007 and HC-REF012 across the in-scope modules."""
    try:
        from honest_check import run_seam_rules
    except ImportError as exc:
        return [f"cannot import run_seam_rules: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        declarations = {}
        paths = {}
        for src in case["modules"]:
            module = read_hd(src)["ok"]["modules"][0]
            declarations[module["name"]] = module
            paths[module["name"]] = f"{module['name']}/{module['name']}.hd"
        got = run_seam_rules(
            declarations=declarations,
            paths=paths,
            manifest_deps=case["manifest_deps"],
            in_scope=case["in_scope"],
        )
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        if pairs != case["expect"]:
            bad.append(
                f"run_seam_rules(in_scope={case['in_scope']!r}, "
                f"manifest_deps={case['manifest_deps']!r}) -> {pairs!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
