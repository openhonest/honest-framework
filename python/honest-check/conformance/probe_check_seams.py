"""Honest probe for honest-check's check_seams (feature Scenario: check_seams).

check_seams is the single door the honest-pre-commit dogfood gate reaches into
the cross-module seam checks. It hands its three inputs straight to
run_seam_rules and returns the combined diagnostic list, holding no resolution
logic itself. So it must return the flat list of every HC-REF006 and HC-REF007
Diagnostic over the in-scope modules (resolved against every declaration).

The firing case declares one caller with two seams into one target: a dead door
(ghost -> HC-REF006) and a wrong-role door (plain, a `fn` -> HC-REF007), and
pins the two diagnostics in 006-before-007 order. The resolved case points the
seam at a boundary_in door and pins the empty list. A stub `return []` passes the
resolved case and fails the firing case.

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

# Each case: caller .hd, target .hd, the in_scope list, and the ordered
# (rule_id, severity) pairs check_seams must return.
_CASES = [
    {
        "caller": _SRC_CALLER_TWO,
        "target": _SRC_TARGET_PLAIN,
        "in_scope": ["caller"],
        "expect": [("HC-REF006", "error"), ("HC-REF007", "error")],
    },
    # Absence: every in-scope seam resolves to a boundary_in door.
    {
        "caller": _SRC_CALLER_GOOD,
        "target": _SRC_TARGET_GOOD,
        "in_scope": ["caller"],
        "expect": [],
    },
]


def probe_check_seams():
    """check_seams returns the combined HC-REF006/HC-REF007 diagnostics for the gate."""
    try:
        from honest_check import check_seams
    except ImportError as exc:
        return [f"cannot import check_seams: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        caller = read_hd(case["caller"])["ok"]["modules"][0]
        target = read_hd(case["target"])["ok"]["modules"][0]
        declarations = {caller["name"]: caller, target["name"]: target}
        paths = {caller["name"]: "caller/caller.hd", target["name"]: "target/target.hd"}
        got = check_seams(
            declarations=declarations,
            paths=paths,
            manifest_deps={},
            in_scope=case["in_scope"],
        )
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        if pairs != case["expect"]:
            bad.append(
                f"check_seams(in_scope={case['in_scope']!r}) -> {pairs!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
