"""check_hc_ref007 fires when a seam names a function that is there and is not a
door: the named module declares the function, but its role is not boundary_in,
so the world reaches that module somewhere other than its entrance.

Pins two cases. Each gives a caller module .hd and a declarations map (both
parsed through honest-design's read_hd, not the function under test). The firing
case names `callee.helper` where callee declares helper as a plain fn and
expects one HC-REF007 error. The clean case has callee declare helper as a
boundary_in and expects no HC-REF007. A stub returning [] fails the firing case.

Spec authority: §HC-REF007 (honest-check-architecture.md §615, §633-636).
"""

# Each case: the caller .hd, the callee .hd whose declaration is loaded, and
# whether HC-REF007 must fire.
_CASES = [
    # callee declares 'helper' as a plain fn, not a boundary_in -> the core is
    # being reached directly.
    {
        "name": "HC-REF007 fires on a non-door target",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.helper"\n',
        "callee_hd": "module callee\n\n  fn helper : (x: str) -> str\n",
        "want_fire": True,
    },
    # callee declares 'helper' as a boundary_in -> the seam enters a door, no finding.
    {
        "name": "clean when the target is a boundary_in",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.helper"\n',
        "callee_hd": "module callee\n\n  boundary_in fn helper : (x: str) -> str\n",
        "want_fire": False,
    },
]


def probe_check_hc_ref007():
    try:
        from honest_check.integration_rules import check_hc_ref007
    except ImportError as exc:
        return [f"cannot import check_hc_ref007: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        caller_parsed = read_hd(case["caller_hd"])
        if "ok" not in caller_parsed:
            bad.append(f"{case['name']}: caller .hd did not parse: {caller_parsed.get('err')!r}")
            continue
        caller = caller_parsed["ok"]["modules"][0]

        callee_parsed = read_hd(case["callee_hd"])
        if "ok" not in callee_parsed:
            bad.append(f"{case['name']}: callee .hd did not parse: {callee_parsed.get('err')!r}")
            continue
        callee = callee_parsed["ok"]["modules"][0]
        declarations = {callee["name"]: callee}

        got = check_hc_ref007(caller, declarations, "caller.hd")
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_hc_ref007 -> {got!r}, expected a list")
            continue

        fired = [d for d in got if d.get("rule_id") == "HC-REF007"]
        if case["want_fire"]:
            if not fired:
                rule_ids = [d.get("rule_id") for d in got]
                bad.append(
                    f"{case['name']}: check_hc_ref007 -> rule_ids {rule_ids}, "
                    f"expected one to be 'HC-REF007'"
                )
            elif not any(d.get("severity") == "error" for d in fired):
                bad.append(
                    f"{case['name']}: HC-REF007 fired at severity "
                    f"{[d.get('severity') for d in fired]}, expected 'error'"
                )
        else:
            if fired:
                bad.append(
                    f"{case['name']}: check_hc_ref007 fired HC-REF007, expected none"
                )
    return bad
