"""check_hc_ref009 reads every loaded declaration at once and raises an information finding when
one module writes a named world resource that another module reads: the two meet through that
resource even though neither names the other, so the reader confirms the coupling is intended.

Pins six cases. Each gives one or more module .hd strings, parsed through honest-design's read_hd
(not the function under test) into the declarations map the rule reads, with each module's path
set to "<name>.hd". The firing case has module `a` write `file:design/data` and module `b` read
it, and expects one HC-REF009 info whose source_location is the writer's path, `a.hd`. The reads_writes
case has `a` read_write `database:mockument` and `b` read it, and fires the same way. The bare-kind
case shares `file`, which couples nobody because it carries no name. The `given` case shares
`database:given`, the reserved run-time name that never matches another. The same-module case has
one module write and read the resource, which is one module meeting itself, not two modules
meeting. The reads-reads case has both modules read the resource and neither write it, so no pair
forms. A stub returning [] passes every case but the two firing ones.

On a firing case the probe pins the diagnostic's fields: the info severity, the exact
source_location (the writer module's path), that context is the empty string and present as a key,
that fixable is the bool False and present as a key, and that the message names the writer module,
the resource, the reader module, and the confirm-the-coupling tail verbatim.

Spec authority: §HC-REF009 (honest-check-architecture.md §717-745).
"""

_CASES = [
    {
        "name": "HC-REF009 fires when two modules meet through a named resource",
        "modules": [
            'module a\n\n  boundary_out fn w : (x: str) -> str side_effect writes "file:design/data"\n',
            'module b\n\n  reader fn r : (x: str) -> str side_effect reads "file:design/data"\n',
        ],
        "writer": "a",
        "want_fire": True,
        "want_message_parts": [
            "'a' writes 'file:design/data' and 'b' reads it",
            "neither names the other. Confirm the coupling is intended.",
        ],
    },
    {
        "name": "HC-REF009 fires on a reads_writes writer",
        "modules": [
            'module a\n\n  boundary_out fn w : (x: str) -> str side_effect reads_writes "database:mockument"\n',
            'module b\n\n  reader fn r : (x: str) -> str side_effect reads "database:mockument"\n',
        ],
        "writer": "a",
        "want_fire": True,
        "want_message_parts": [
            "'a' writes 'database:mockument' and 'b' reads it",
        ],
    },
    {
        "name": "clean when the shared target is a bare kind",
        "modules": [
            'module a\n\n  boundary_out fn w : (x: str) -> str side_effect writes "file"\n',
            'module b\n\n  reader fn r : (x: str) -> str side_effect reads "file"\n',
        ],
        "want_fire": False,
    },
    {
        "name": "clean when the shared name is the reserved given",
        "modules": [
            'module a\n\n  boundary_out fn w : (x: str) -> str side_effect writes "database:given"\n',
            'module b\n\n  reader fn r : (x: str) -> str side_effect reads "database:given"\n',
        ],
        "want_fire": False,
    },
    {
        "name": "clean when one module writes and reads the same resource",
        "modules": [
            'module a\n\n  boundary_out fn w : (x: str) -> str side_effect reads_writes "file:design/data"\n',
        ],
        "want_fire": False,
    },
    {
        "name": "clean when both modules only read the resource",
        "modules": [
            'module a\n\n  reader fn r : (x: str) -> str side_effect reads "file:design/data"\n',
            'module b\n\n  reader fn r : (x: str) -> str side_effect reads "file:design/data"\n',
        ],
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
        if d.get("severity") != "info":
            failures.append(
                f"{name}: firing diagnostic severity {d.get('severity')!r}, expected 'info'"
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


def probe_check_hc_ref009():
    try:
        from honest_check.integration_rules import check_hc_ref009
    except ImportError as exc:
        return [f"cannot import check_hc_ref009: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        declarations = {}
        paths = {}
        parse_failed = False
        for hd in case["modules"]:
            parsed = read_hd(hd)
            if "ok" not in parsed:
                bad.append(f"{case['name']}: a module .hd did not parse: {parsed.get('err')!r}")
                parse_failed = True
                break
            module = parsed["ok"]["modules"][0]
            declarations[module["name"]] = module
            paths[module["name"]] = f"{module['name']}.hd"
        if parse_failed:
            continue

        got = check_hc_ref009(declarations, [], paths)
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_hc_ref009 -> {got!r}, expected a list")
            continue

        fired = [d for d in got if d.get("rule_id") == "HC-REF009"]
        if case["want_fire"]:
            if not fired:
                rule_ids = [d.get("rule_id") for d in got]
                bad.append(
                    f"{case['name']}: check_hc_ref009 -> rule_ids {rule_ids}, "
                    f"expected one to be 'HC-REF009'"
                )
            else:
                bad.extend(
                    _field_failures(
                        case["name"], fired, case["want_message_parts"], f"{case['writer']}.hd"
                    )
                )
        else:
            if fired:
                bad.append(
                    f"{case['name']}: check_hc_ref009 fired HC-REF009, expected none"
                )
    return bad
