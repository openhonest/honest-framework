"""check_hc_ref008 fires when a side effect names a module in view but carries no
door: the caller reaches another module and tells the resolver nothing it can act
on, as in `writes "honest-persist"`. The door must be named.

Pins five cases. Each gives a caller module .hd and a declarations map (both
parsed through honest-design's read_hd, not the function under test). The dotless
case names `callee` with no dot and expects one HC-REF008 error, because
honest-check resolves the bare name against the module list (the ruling that
honest-check matches the dotless name, not honest-design). The trailing-dot case
names `callee.` and expects one HC-REF008 error. The clean case names
`callee.door`, a named door, and expects no HC-REF008. The skip case leaves callee
out of declarations and expects nothing (a world target or a module out of view,
skipped not assumed absent, §639). The world case reads `HTTP` and expects
nothing. A stub returning [] passes every case but the two firing ones.

On a firing case the probe pins the diagnostic's fields: the exact
source_location ("caller.hd"), that context is the empty string and present as a
key, that fixable is the bool False and present as a key, and that the message
names the caller function, the direction, the module, and the names-a-module tail
verbatim.

Spec authority: §HC-REF008 (honest-check-architecture.md §696-715).
"""

_CASES = [
    # A dotless target that matches a module in view -> disguised seam, no door.
    {
        "name": "HC-REF008 fires on a dotless module name",
        "caller_hd": 'module caller\n\n  boundary_out fn f : (x: str) -> str side_effect writes "callee"\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": True,
        "want_message_parts": [
            "'f' writes 'callee', which names a module and not a door.",
            "Name the function it enters, as 'callee.<door>'.",
        ],
    },
    # The trailing-dot form: module named, door half empty.
    {
        "name": "HC-REF008 fires on a trailing-dot module name",
        "caller_hd": 'module caller\n\n  boundary_out fn f : (x: str) -> str side_effect writes "callee."\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": True,
        "want_message_parts": ["'f' writes 'callee', which names a module and not a door."],
    },
    # A named door resolves, so this is HC-REF006/007's to judge, not HC-REF008's.
    {
        "name": "clean when the seam names a door",
        "caller_hd": 'module caller\n\n  boundary_out fn f : (x: str) -> str side_effect writes "callee.door"\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": False,
    },
    # The named module is not in view -> a world target or a module out of view, skipped.
    {
        "name": "skip when the named module is not in view",
        "caller_hd": 'module caller\n\n  boundary_out fn f : (x: str) -> str side_effect writes "callee"\n',
        "callee_hd": None,
        "want_fire": False,
    },
    # A world target matches no module, so it is never a seam.
    {
        "name": "skip a world target",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "HTTP"\n',
        "callee_hd": "module callee\n\n  boundary_in fn door : (x: str) -> str\n",
        "want_fire": False,
    },
]


def _field_failures(name, diagnostics, parts, path):
    failures = []
    for d in diagnostics:
        message = d.get("message", "")
        for part in parts:
            if part not in message:
                failures.append(
                    f"{name}: firing diagnostic message {message!r} is missing {part!r}"
                )
        if d.get("source_location") != path:
            failures.append(
                f"{name}: firing diagnostic source_location "
                f"{d.get('source_location')!r}, expected {path!r}"
            )
        if "context" not in d or d["context"] != "":
            failures.append(
                f"{name}: firing diagnostic context {d.get('context')!r}, "
                f"expected '' present as a key"
            )
        if "fixable" not in d or d["fixable"] is not False:
            failures.append(
                f"{name}: firing diagnostic fixable {d.get('fixable')!r}, "
                f"expected False present as a key"
            )
    return failures


def probe_check_hc_ref008():
    try:
        from honest_check.integration_rules import check_hc_ref008
    except ImportError as exc:
        return [f"cannot import check_hc_ref008: {exc}"]
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

        got = check_hc_ref008(caller, declarations, "caller.hd")
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_hc_ref008 -> {got!r}, expected a list")
            continue

        fired = [d for d in got if d.get("rule_id") == "HC-REF008"]
        if case["want_fire"]:
            if not fired:
                rule_ids = [d.get("rule_id") for d in got]
                bad.append(
                    f"{case['name']}: check_hc_ref008 -> rule_ids {rule_ids}, "
                    f"expected one to be 'HC-REF008'"
                )
            elif not any(d.get("severity") == "error" for d in fired):
                bad.append(
                    f"{case['name']}: HC-REF008 fired at severity "
                    f"{[d.get('severity') for d in fired]}, expected 'error'"
                )
            if fired:
                bad.extend(
                    _field_failures(
                        case["name"], fired, case["want_message_parts"], "caller.hd"
                    )
                )
        else:
            if fired:
                bad.append(
                    f"{case['name']}: check_hc_ref008 fired HC-REF008, expected none"
                )
    return bad
