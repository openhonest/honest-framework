"""The cross-module seam rules — HC-REF006 and HC-REF007 — and the derivation they share.

A declaration never crosses a module boundary: the caller names the callee's door on its own
side effect, with a dot (`reads "honest-parse.parse_source"`), and the callee never names its
callers, which is what lets a library be used by code it has never heard of. So a seam is
written once, by the side that knows, and resolving it needs both the caller's declaration and
the callee's in view at the same time. `validate` sees one module and reports nothing here;
resolving a reference across modules is honest-check's, like every other reference that resolves
or does not (§HC-REF006/HC-REF007, honest-check-architecture.md §607-639).

These three are pure. They open no file and execute no application code — the gate supplies the
declarations and the rule judges only those. They raise nothing: a dead or misdirected seam
comes back as a Diagnostic, because a violation is data (section 8).

The honest-pre-commit gate imports the two check functions and declared_seams from this submodule by
path; they are defined here (so HC-REF005's "defined somewhere" holds) and not re-exported from
the package __init__ (so no export the .hd does not declare).
"""


def check_seams(declarations, paths, in_scope):
    """The door the honest-pre-commit dogfood gate calls to run honest-check's cross-module seam checks
    (section 8, §HC-REF006/§HC-REF007). It is the single entry point the external gate reaches
    into these checks.

    It carries only I/O: it hands its three inputs straight to the orchestrator run_seam_rules and
    returns the combined diagnostic list the orchestrator produced, holding no resolution logic
    itself. declarations is every loaded module's parsed declaration keyed by its module name;
    paths is each module's .hd filesystem path keyed by the same name; in_scope is the module
    names to report on (the empty list meaning the whole framework, every loaded module). It
    reads no world and writes none: the gate supplies the declarations already parsed. It raises
    nothing — an unresolved seam comes back as a Diagnostic.
    """
    return run_seam_rules(declarations, paths, in_scope)


def run_seam_rules(declarations, paths, in_scope):
    """The orchestrator the seam door hands its inputs to (section 8, §HC-REF006/§HC-REF007). For
    each module named in in_scope — or every loaded module when in_scope is empty — it runs the
    two cross-module seam rules over that module's declaration and folds every finding into one
    list.

    For each in-scope module it calls check_hc_ref006 with the module's declaration, the whole
    declarations map and the module's .hd path, then check_hc_ref007 the same way, concatenating
    their diagnostics in that order across every in-scope module. Both rules derive the module's
    seams themselves through declared_seams, so the orchestrator never derives seams here. Each
    in-scope module's seams resolve against the COMPLETE declarations map, not the in-scope
    subset, so the gate's verdict on a module never changes with how it was invoked (§639). An
    in-scope name absent from declarations is skipped, the same skip posture the rules take for an
    out-of-view module: a workspace holds the modules it holds. It returns the flat combined list,
    empty when every in-scope module's seams resolve; it raises nothing.
    """
    targets = in_scope if in_scope else list(declarations)
    findings = []
    for name in targets:
        if name not in declarations:
            continue
        module = declarations[name]
        path = paths[name]
        findings.extend(check_hc_ref006(module, declarations, path))
        findings.extend(check_hc_ref007(module, declarations, path))
    return findings


def declared_seams(module):
    """Collect every cross-module seam one module declares into a list of Seam records, the one
    derivation HC-REF006 and HC-REF007 share rather than each re-deriving it (§HC-REF006).

    For each function in module.functions and each side effect that function declares: a side
    effect whose module half is the empty string names the world — `reads "HTTP"`,
    `writes "DOM"`, `reads "env:POOL_SIZE"` — and carries no module to resolve, so it is skipped;
    a side effect whose module half is non-empty is a cross-module seam and becomes one Seam
    carrying the function's name as the caller, the named module, the door (the side effect's
    door half, which may be the empty string when the target named a module and no door), and
    the direction. The list is empty when the module declares no cross-module side effect.
    """
    return [
        {
            "caller": function["name"],
            "module": side["module"],
            "door": side["door"],
            "direction": side["direction"],
        }
        for function in module["functions"]
        for side in function["side_effects"]
        if side["module"] != ""
    ]


def check_hc_ref006(module, declarations, path):
    """Run HC-REF006 over the seams one module declares: a seam into a module that IS present in
    declarations but that declares no function of the seam's door name is a dead reference, and
    emits one HC-REF006 error (§HC-REF006, §613, §639).

    Two skips precede resolving each seam. A seam whose door is the empty string names a module
    and no door and carries nothing to resolve, so it is skipped — that bare-module case is
    HC-REF008's, not this rule's. A seam whose named module is not a key in declarations is
    skipped, not assumed absent: a workspace holds the modules it holds, a declaration may name
    one from outside it, and a gate whose answer changes with how it was invoked is not a gate
    (§639). The caller supplies the declarations; path is stamped into each diagnostic's
    source_location so a reader finds the offending side effect.
    """
    findings = []
    for seam in declared_seams(module):
        if seam["door"] == "":
            continue
        if seam["module"] not in declarations:
            continue
        callee = declarations[seam["module"]]
        declared_doors = {function["name"] for function in callee["functions"]}
        if seam["door"] not in declared_doors:
            findings.append(
                {
                    "rule_id": "HC-REF006",
                    "severity": "error",
                    "message": (
                        f"'{seam['caller']}' {seam['direction']} "
                        f"'{seam['module']}.{seam['door']}', and {seam['module']} declares no "
                        "function of that name."
                    ),
                    "source_location": path,
                    "context": "",
                    "fixable": False,
                }
            )
    return findings


def check_hc_ref007(module, declarations, path):
    """Run HC-REF007 over the seams one module declares: a seam whose door name IS declared in
    the named module but whose role is neither boundary_in nor edge reaches that module somewhere
    other than its entrance, and emits one HC-REF007 error (§HC-REF007, §615, §633-636).

    A module has two kinds of entrance. A boundary_in is a door where the world calls in; an edge
    is the pure import surface a library publishes and names with an entry. A seam landing on
    either lands on a declared entrance, so both are accepted. A pure library with no boundaries,
    like honest-type, has only edges. The fault is a seam landing on a plain fn that no entry
    names: that function is interior, so the seam uses the core directly.

    The same two skips HC-REF006 applies hold here: a seam whose door is the empty string is
    skipped (HC-REF008's case), and a seam whose named module is not a key in declarations is
    skipped, not assumed absent (§639). Only a seam whose named module is in declarations AND
    declares a function of the seam's door name is resolved; if that function's role is neither
    boundary_in nor edge, it emits one HC-REF007 error naming the role the module gave that door.
    """
    findings = []
    for seam in declared_seams(module):
        if seam["door"] == "":
            continue
        if seam["module"] not in declarations:
            continue
        callee = declarations[seam["module"]]
        role_of = {function["name"]: function["role"] for function in callee["functions"]}
        if seam["door"] in role_of and role_of[seam["door"]] not in ("boundary_in", "edge"):
            findings.append(
                {
                    "rule_id": "HC-REF007",
                    "severity": "error",
                    "message": (
                        f"'{seam['caller']}' {seam['direction']} "
                        f"'{seam['module']}.{seam['door']}', which {seam['module']} declares as "
                        f"a {role_of[seam['door']]} and not an entrance."
                    ),
                    "source_location": path,
                    "context": "",
                    "fixable": False,
                }
            )
    return findings
