# scenario: check_hc_ref006
# inherits: hd=python/honest-check/honest-check.hd::check_hc_ref006 -> feature=specs/features/honest-check.feature::check_hc_ref006
"""Honest probe for honest-check's check_hc_ref006 (feature Scenario: check_hc_ref006).

check_hc_ref006 runs HC-REF006 over the seams one module declares: for a seam
into a module that IS present in declarations but that declares no function of
the seam's door name, it emits one HC-REF006 error naming the caller, the module
and the door. It skips a seam whose door is empty (HC-REF008's case) and a seam
whose named module is absent from declarations (not assumed dead, because a gate
whose answer changes with how it was invoked is not a gate). The dead-door case
pins one HC-REF006 error; the resolved case (the door names a real function) is
the explicit absence, emitting nothing. A stub `return []` passes the resolved
case and fails the dead-door case.

Inputs are real Declarations parsed by honest-design's read_hd.

Note: the task named this slot "check_hc_ref"; no such function is declared. The
cross-module door rules are check_hc_ref006 and check_hc_ref007 (feature +
honest-check.hd), probed in their own files.
"""

# caller.calling_step reaches target.ghost; target declares no ghost -> HC-REF006.
_SRC_CALLER_GHOST = (
    "module caller\n\n"
    '  fn calling_step : (x: str) -> str side_effect reads "target.ghost"\n'
)
# caller.c reaches target.present; target declares present -> resolved, no finding.
_SRC_CALLER_PRESENT = (
    "module caller\n\n"
    '  fn c : (x: str) -> str side_effect reads "target.present"\n'
)
_SRC_TARGET = (
    "module target\n\n"
    "  fn present : (x: str) -> str\n"
)

# Each case: caller .hd, the target module .hd that gets keyed into declarations,
# and the (rule_id, severity) pairs check_hc_ref006 must return.
_CASES = [
    {
        "caller": 'module caller\n\n  fn c : () -> str side_effect reads "target"\n',
        "target": _SRC_TARGET,
        "expect": [],
    },
    {
        "caller": 'module caller\n\n  fn c : () -> str side_effect reads "not-loaded.door"\n',
        "target": _SRC_TARGET,
        "expect": [],
    },
    {"caller": _SRC_CALLER_GHOST, "target": _SRC_TARGET, "expect": [("HC-REF006", "error")]},
    # Absence: every door the module names resolves to a function in the target.
    {"caller": _SRC_CALLER_PRESENT, "target": _SRC_TARGET, "expect": []},
]


def probe_check_hc_ref006():
    """check_hc_ref006 flags each seam into a module missing the named door."""
    try:
        from honest_check import check_hc_ref006
    except ImportError as exc:
        return [f"cannot import check_hc_ref006: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        caller = read_hd(case["caller"])["ok"]["modules"][0]
        target = read_hd(case["target"])["ok"]["modules"][0]
        declarations = {caller["name"]: caller, target["name"]: target}
        got = check_hc_ref006(module=caller, declarations=declarations, path="target/target.hd")
        for finding in got:
            if not all(word in finding["message"] for word in ("calling_step", "target.ghost")):
                bad.append(f"unexpected seam message: {finding!r}")
            if finding["source_location"] != "target/target.hd":
                bad.append(f"incorrect seam diagnostic location: {finding!r}")
            if finding["context"] != "" or finding["fixable"] is not False:
                bad.append(f"unexpected context or automatic fix on seam finding: {finding!r}")
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        if pairs != case["expect"]:
            bad.append(
                f"check_hc_ref006({case['caller']!r}) -> {pairs!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
