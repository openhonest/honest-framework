# scenario: check_hc_ref007
# inherits: hd=python/honest-check/honest-check.hd::check_hc_ref007 -> feature=specs/features/honest-check.feature::check_hc_ref007
"""Honest probe for honest-check's check_hc_ref007 (feature Scenario: check_hc_ref007).

check_hc_ref007 runs HC-REF007 over the seams one module declares: for a seam
whose door name IS declared in the named module but whose role is not
boundary_in, it emits one HC-REF007 error naming the caller, the module, the
door and the role. It applies the same two skips as HC-REF006 (door empty, named
module absent from declarations). The wrong-role case pins one HC-REF007 error
(the door is a plain `fn`, reached other than through an entrance); the
boundary_in case is the explicit absence, emitting nothing. A stub `return []`
passes the boundary_in case and fails the wrong-role case.

Inputs are real Declarations parsed by honest-design's read_hd.

Note: the task named this slot "check_hc_ref"; no such function is declared. The
cross-module door rules are check_hc_ref006 and check_hc_ref007 (feature +
honest-check.hd), probed in their own files.
"""

# caller.calling_step reaches target.plain; target declares plain with role fn -> HC-REF007.
_SRC_CALLER_PLAIN = (
    "module caller\n\n"
    '  fn calling_step : (x: str) -> str side_effect reads "target.plain"\n'
)
# caller.c reaches target.good; target declares good as boundary_in -> resolved.
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

# Each case: caller .hd, target .hd, and the (rule_id, severity) pairs returned.
_CASES = [
    {
        "caller": 'module caller\n\n  fn c : () -> str side_effect reads "target"\n',
        "target": _SRC_TARGET_GOOD,
        "expect": [],
    },
    {
        "caller": 'module caller\n\n  fn c : () -> str side_effect reads "not-loaded.door"\n',
        "target": _SRC_TARGET_GOOD,
        "expect": [],
    },
    {"caller": _SRC_CALLER_PLAIN, "target": _SRC_TARGET_PLAIN, "expect": [("HC-REF007", "error")]},
    # Absence: the door the module names is a boundary_in of the target.
    {"caller": _SRC_CALLER_GOOD, "target": _SRC_TARGET_GOOD, "expect": []},
]


def probe_check_hc_ref007():
    """check_hc_ref007 flags each seam onto a door that is not a boundary_in."""
    try:
        from honest_check import check_hc_ref007
    except ImportError as exc:
        return [f"cannot import check_hc_ref007: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        caller = read_hd(case["caller"])["ok"]["modules"][0]
        target = read_hd(case["target"])["ok"]["modules"][0]
        declarations = {caller["name"]: caller, target["name"]: target}
        got = check_hc_ref007(module=caller, declarations=declarations, path="target/target.hd")
        for finding in got:
            if not all(word in finding["message"] for word in ("calling_step", "target.plain", "fn")):
                bad.append(f"unexpected seam message: {finding!r}")
            if finding["source_location"] != "target/target.hd":
                bad.append(f"incorrect seam diagnostic location: {finding!r}")
            if finding["context"] != "" or finding["fixable"] is not False:
                bad.append(f"unexpected context or automatic fix on seam finding: {finding!r}")
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        if pairs != case["expect"]:
            bad.append(
                f"check_hc_ref007({case['caller']!r}) -> {pairs!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
