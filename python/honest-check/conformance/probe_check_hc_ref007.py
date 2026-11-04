"""check_hc_ref007 fires when a seam names a function that is there and is not a
door: the named module declares the function, but its role is not boundary_in,
so the world reaches that module somewhere other than its entrance.

Pins two cases. Each gives a caller module .hd and a declarations map (both
parsed through honest-design's read_hd, not the function under test). The firing
case names `callee.helper` where callee declares helper as a plain fn and
expects one HC-REF007 error. The clean case has callee declare helper as a
boundary_in and expects no HC-REF007. A stub returning [] fails the firing case.

On the firing case the probe also pins the diagnostic's fields, not just that it
fired: the exact source_location ("caller.hd"), that context is the empty string
and present as a key, that fixable is the bool False and present as a key, and
that the message names the caller function, the direction, the module and door,
the role the module gave the door, and the not-an-entrance tail verbatim. This holds
the message text, the source_location, the context and fixable fields against a
rule that fires with an empty or mislabelled diagnostic.

Spec authority: §HC-REF007 (honest-check-architecture.md §615, §633-636).
"""

# Each case: the caller .hd, the callee .hd whose declaration is loaded, and
# whether HC-REF007 must fire. The firing case also carries the message parts
# the diagnostic must contain verbatim.
_CASES = [
    # callee declares 'helper' as a plain fn, not a boundary_in -> the core is
    # being reached directly.
    {
        "name": "HC-REF007 fires on a non-door target",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.helper"\n',
        "callee_hd": "module callee\n\n  fn helper : (x: str) -> str\n",
        "want_fire": True,
        "want_message_parts": [
            "'f' reads ",
            "'callee.helper', which callee declares as ",
            "a fn and not an entrance.",
        ],
    },
    # callee declares 'helper' as a boundary_in -> the seam enters a door, no finding.
    {
        "name": "clean when the target is a boundary_in",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.helper"\n',
        "callee_hd": "module callee\n\n  boundary_in fn helper : (x: str) -> str\n",
        "want_fire": False,
    },
    # callee declares 'helper' as an edge -> the pure import surface a library
    # publishes is a declared entrance, so the seam lands on it cleanly. This is
    # honest-type's case: no boundaries, only edges.
    {
        "name": "clean when the target is an edge",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee.helper"\n',
        "callee_hd": "module callee\n\n  edge fn helper : (x: str) -> str\n",
        "want_fire": False,
    },
    # A seam naming a module and no door (door empty) is skipped: that bare-module
    # case is HC-REF008's, not this rule's.
    {
        "name": "skip a bare-module seam with no door",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "callee."\n',
        "callee_hd": "module callee\n\n  fn helper : (x: str) -> str\n",
        "want_fire": False,
    },
    # A seam whose named module is not in declarations is skipped, not assumed
    # absent (§639): the caller names 'missing', only 'callee' is in view.
    {
        "name": "skip when the named module is not in view",
        "caller_hd": 'module caller\n\n  reader fn f : (r: str) -> str side_effect reads "missing.helper"\n',
        "callee_hd": "module callee\n\n  fn helper : (x: str) -> str\n",
        "want_fire": False,
    },
]


def _field_failures(name, diagnostics, parts, path):
    """Field-level checks on the firing seam diagnostics: each pins the exact
    source_location, that context is the empty string and present as a key, that
    fixable is the bool False and present as a key, and that the message carries
    every named part verbatim."""
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
            if fired:
                bad.extend(
                    _field_failures(
                        case["name"], fired, case["want_message_parts"], "caller.hd"
                    )
                )
        else:
            if fired:
                bad.append(
                    f"{case['name']}: check_hc_ref007 fired HC-REF007, expected none"
                )
    return bad
