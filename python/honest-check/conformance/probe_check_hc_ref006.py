"""check_hc_ref006 fires when a seam names a door the named module does not
declare: the caller says it enters M.d, M declares no function d, the reference
is dead.

Pins three cases. Each gives a caller module .hd and a declarations map (both
parsed through honest-design's read_hd, not the function under test). The firing
case names `callee.ghost` where callee declares no ghost and expects one
HC-REF006 error. The clean case has callee declare ghost and expects no
HC-REF006. The skip case leaves callee out of declarations and expects no
finding (skipped, not assumed absent, §639). A stub returning [] passes the
clean and skip cases but fails the firing case.

Spec authority: §HC-REF006 (honest-check-architecture.md §613, §639).
"""

# Each case: the caller .hd, the callee .hd whose declaration is loaded (or None
# to leave it out of the map), and whether HC-REF006 must fire.
_CASES = [
    # callee IS loaded and declares no function named 'ghost' -> dead reference.
    {
        "name": "HC-REF006 fires on a dead door name",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.ghost"\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": True,
    },
    # callee IS loaded and declares 'ghost' -> the door name resolves, no finding.
    {
        "name": "clean when the door name resolves",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.ghost"\n',
        "callee_hd": "module callee\n\n  boundary_in fn ghost : (x: str) -> str\n",
        "want_fire": False,
    },
    # callee is NOT loaded -> skipped, not assumed absent.
    {
        "name": "skip when the named module is not in view",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.ghost"\n',
        "callee_hd": None,
        "want_fire": False,
    },
    # A seam naming a module and no door (door empty) is HC-REF008's case, not
    # this rule's, so HC-REF006 skips it even though callee is in view.
    {
        "name": "skip a bare-module seam with no door",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee."\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": False,
    },
]


def probe_check_hc_ref006():
    try:
        from honest_check.integration_rules import check_hc_ref006
    except ImportError as exc:
        return [f"cannot import check_hc_ref006: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        caller_parsed = read_hd(case["caller_hd"])
        if "ok" not in caller_parsed:
            bad.append(f"{case['name']}: caller .hd did not parse: {caller_parsed.get('err')!r}")
            continue
        caller = caller_parsed["ok"]["modules"][0]

        declarations = {}
        if case["callee_hd"] is not None:
            callee_parsed = read_hd(case["callee_hd"])
            if "ok" not in callee_parsed:
                bad.append(f"{case['name']}: callee .hd did not parse: {callee_parsed.get('err')!r}")
                continue
            callee = callee_parsed["ok"]["modules"][0]
            declarations[callee["name"]] = callee

        got = check_hc_ref006(caller, declarations, "caller.hd")
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_hc_ref006 -> {got!r}, expected a list")
            continue

        fired = [d for d in got if d.get("rule_id") == "HC-REF006"]
        if case["want_fire"]:
            if not fired:
                rule_ids = [d.get("rule_id") for d in got]
                bad.append(
                    f"{case['name']}: check_hc_ref006 -> rule_ids {rule_ids}, "
                    f"expected one to be 'HC-REF006'"
                )
            elif not any(d.get("severity") == "error" for d in fired):
                bad.append(
                    f"{case['name']}: HC-REF006 fired at severity "
                    f"{[d.get('severity') for d in fired]}, expected 'error'"
                )
        else:
            if fired:
                bad.append(
                    f"{case['name']}: check_hc_ref006 fired HC-REF006, expected none"
                )
    return bad
