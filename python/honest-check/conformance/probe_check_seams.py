"""check_seams is the honest-pre-commit gate door that routes the seam inputs to the
orchestrator (feature: "check_seams is the honest-pre-commit gate door that routes the
seam inputs to the orchestrator").

The door takes (declarations, paths, in_scope), hands them straight to
run_seam_rules, and returns the same combined Diagnostic list. So its observable
behaviour matches the orchestrator's: a dead seam comes back as an HC-REF006
error, a seam onto a non-door comes back as an HC-REF007 error, a seam from an
out-of-scope module is not reported, and a resolved workspace returns [].

Every case builds its modules from real .hd strings parsed by honest-design's
read_hd (not the function under test), keys declarations and paths by each
module's name, and names the in-scope set. Four cases pin:

  - FIRING HC-REF006: module a declares a seam `reads "b.ghost"`; module b
    declares no function ghost. With a and b both in scope the result contains an
    HC-REF006 error — a dead reference.
  - FIRING HC-REF007: module a declares a seam `reads "b.helper"`; module b
    declares helper as a plain fn, not a boundary_in. The result contains an
    HC-REF007 error — the core reached somewhere other than its door.
  - SCOPE: the same a-into-b.ghost seam, but in_scope is ["b"] only, with a out
    of scope. a's dead seam is NOT reported (no HC-REF006 fires).
  - CLEAN: module a declares a seam `reads "b.realdoor"`; module b declares
    realdoor as a boundary_in. With both in scope the result is [].

A stub returning [] passes the scope and clean cases but fails both firing
cases, so the probe is not vacuous.

Spec authority: specs/features/honest-check.feature, scenario "check_seams is
the honest-pre-commit gate door that routes the seam inputs to the orchestrator".
"""

# Each module's .hd text, reused across cases.
_A_GHOST = 'module a\n\n  reader fn f : (r: str) -> str side_effect reads "b.ghost"\n'
_A_HELPER = 'module a\n\n  reader fn f : (r: str) -> str side_effect reads "b.helper"\n'
_A_REALDOOR = 'module a\n\n  reader fn f : (r: str) -> str side_effect reads "b.realdoor"\n'

_B_NO_GHOST = "module b\n\n  boundary_in fn realdoor : (x: str) -> str\n"
_B_HELPER_PLAIN = "module b\n\n  fn helper : (x: str) -> str\n"
_B_REALDOOR_DOOR = "module b\n\n  boundary_in fn realdoor : (x: str) -> str\n"

_CASES = [
    {
        "name": "HC-REF006 fires on a dead seam when both modules are in scope",
        "modules": {"a": _A_GHOST, "b": _B_NO_GHOST},
        "in_scope": ["a", "b"],
        "expect": {"kind": "fires", "rule": "HC-REF006"},
    },
    {
        "name": "HC-REF007 fires on a seam onto a non-door when both are in scope",
        "modules": {"a": _A_HELPER, "b": _B_HELPER_PLAIN},
        "in_scope": ["a", "b"],
        "expect": {"kind": "fires", "rule": "HC-REF007"},
    },
    {
        "name": "a's dead seam is not reported when a is out of scope",
        "modules": {"a": _A_GHOST, "b": _B_NO_GHOST},
        "in_scope": ["b"],
        "expect": {"kind": "absent", "rule": "HC-REF006"},
    },
    {
        "name": "clean when the seam resolves to a boundary_in",
        "modules": {"a": _A_REALDOOR, "b": _B_REALDOOR_DOOR},
        "in_scope": ["a", "b"],
        "expect": {"kind": "empty"},
    },
]


def probe_check_seams():
    try:
        from honest_check.integration_rules import check_seams
    except ImportError as exc:
        return [f"cannot import check_seams: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        declarations = {}
        paths = {}
        parse_failed = False
        for name, text in case["modules"].items():
            parsed = read_hd(text)
            if "ok" not in parsed:
                bad.append(f"{case['name']}: module {name} .hd did not parse: {parsed.get('err')!r}")
                parse_failed = True
                break
            declaration = parsed["ok"]["modules"][0]
            declarations[declaration["name"]] = declaration
            paths[declaration["name"]] = f"{name}.hd"
        if parse_failed:
            continue

        got = check_seams(declarations, paths, case["in_scope"])
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_seams -> {got!r}, expected a list")
            continue

        expect = case["expect"]
        if expect["kind"] == "fires":
            fired = [d for d in got if d.get("rule_id") == expect["rule"]]
            if not fired:
                rule_ids = [d.get("rule_id") for d in got]
                bad.append(
                    f"{case['name']}: check_seams -> rule_ids {rule_ids}, "
                    f"expected one to be {expect['rule']!r}"
                )
            elif not any(d.get("severity") == "error" for d in fired):
                bad.append(
                    f"{case['name']}: {expect['rule']} fired at severity "
                    f"{[d.get('severity') for d in fired]}, expected 'error'"
                )
        elif expect["kind"] == "absent":
            fired = [d for d in got if d.get("rule_id") == expect["rule"]]
            if fired:
                bad.append(
                    f"{case['name']}: check_seams fired {expect['rule']}, expected none"
                )
        elif expect["kind"] == "empty":
            if got != []:
                bad.append(
                    f"{case['name']}: check_seams -> {got!r}, expected []"
                )
    return bad
