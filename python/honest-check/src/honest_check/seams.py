"""The cross-module seam checks (§8, §HC-REF006/§HC-REF007/§HC-REF012). The gate
loads every module's parsed declaration and reaches one door, check_seams, which
runs the three cross-module rules over the in-scope modules. The rules are pure: a
declaration arrives already parsed, so nothing here opens a file."""

from ._util import choose, pick, read_or


# The closed world-token vocabulary: a bare side-effect target naming one of these
# (or carrying a ':' env marker, or written all-uppercase) names the world, not a
# module. honest-design leaves a bare module target's `module` field empty, so a
# bare module name is told from a world token here rather than by that field alone.
_WORLD_TOKENS = {
    "DOM", "HTTP", "HTTPS", "file", "stdin", "stdout", "stderr", "clock", "random",
    "time", "network", "env", "argv", "process",
}


def _is_world(target):
    return bool(target in _WORLD_TOKENS or ":" in target or target.isupper())


def _bare_seam(caller, effect):
    target = effect["target"]
    return pick(
        _is_world(target),
        lambda: [],
        lambda: [{"caller": caller, "module": target, "door": "", "direction": effect["direction"]}],
    )


def _seam_of(caller, effect):
    return pick(
        effect["module"] != "",
        lambda: [
            {"caller": caller, "module": effect["module"], "door": effect["door"], "direction": effect["direction"]}
        ],
        lambda: _bare_seam(caller, effect),
    )


def declared_seams(module):
    """Every cross-module seam one module declares — one per side effect whose target
    names another module; a world-named side effect is skipped (§8). A bare module
    target (whose declaration-parsed `module` field is empty) is kept when it is not
    a world token."""
    out = []
    for function in module["functions"]:
        caller = function["name"]
        for effect in read_or(function, "side_effects", []):
            out.extend(_seam_of(caller, effect))
    return out


def _seam_diagnostic(rule_id, path, message):
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": message,
        "source_location": path,
        "context": "",
        "fixable": rule_id in frozenset(),
    }


def _ref006_check(seam, declarations, path):
    target = declarations[seam["module"]]
    has_door = any(fn["name"] == seam["door"] for fn in target["functions"])
    return pick(
        has_door,
        lambda: [],
        lambda: [
            _seam_diagnostic(
                "HC-REF006", path,
                f"{seam['caller']} enters {seam['module']}.{seam['door']}, which module {seam['module']} declares no function of",
            )
        ],
    )


def _ref006_one(seam, declarations, path):
    skip = seam["door"] == "" or seam["module"] not in declarations
    return pick(skip, lambda: [], lambda: _ref006_check(seam, declarations, path))


def check_hc_ref006(module, declarations, path):
    """HC-REF006: a seam into a present module that declares no function of the
    named door is a dead reference (§HC-REF006)."""
    out = []
    for seam in declared_seams(module):
        out.extend(_ref006_one(seam, declarations, path))
    return out


def _ref007_check(seam, declarations, path):
    target = declarations[seam["module"]]
    function = next(filter(lambda f: f["name"] == seam["door"], target["functions"]), None)
    return pick(
        function is None or function["role"] == "boundary_in",
        lambda: [],
        lambda: [
            _seam_diagnostic(
                "HC-REF007", path,
                f"{seam['caller']} enters {seam['module']}.{seam['door']}, a {function['role']}, not a boundary_in",
            )
        ],
    )


def _ref007_one(seam, declarations, path):
    skip = seam["door"] == "" or seam["module"] not in declarations
    return pick(skip, lambda: [], lambda: _ref007_check(seam, declarations, path))


def check_hc_ref007(module, declarations, path):
    """HC-REF007: a seam onto a declared door that is not a boundary_in reaches the
    module somewhere other than its entrance (§HC-REF007)."""
    out = []
    for seam in declared_seams(module):
        out.extend(_ref007_one(seam, declarations, path))
    return out


def _ref012_one(dependency, seam_modules, workspace, path):
    skip = dependency not in workspace
    return pick(
        skip,
        lambda: [],
        lambda: pick(
            dependency in seam_modules,
            lambda: [],
            lambda: [
                _seam_diagnostic(
                    "HC-REF012", path,
                    f"the manifest depends on workspace module {dependency}, which the declaration names no seam onto",
                )
            ],
        ),
    )


def check_ref012(module, manifest_deps, workspace_module_names, path):
    """HC-REF012: a workspace module the manifest depends on but the declaration names
    no cross-module seam onto is an undeclared coupling (§HC-REF012)."""
    seam_modules = set(s["module"] for s in declared_seams(module))
    out = []
    for dependency in manifest_deps:
        out.extend(_ref012_one(dependency, seam_modules, workspace_module_names, path))
    return out


def run_seam_rules(declarations, paths, manifest_deps, in_scope):
    """The seam orchestrator (§8): run HC-REF006, HC-REF007 and HC-REF012 over each
    in-scope module, resolving seams against the complete declarations map."""
    scope = choose(len(in_scope) == 0, list(declarations.keys()), in_scope)
    workspace = list(declarations.keys())
    out = []
    for name in scope:
        module = declarations[name]
        path = read_or(paths, name, "")
        dependencies = read_or(manifest_deps, name, [])
        out.extend(check_hc_ref006(module, declarations, path))
        out.extend(check_hc_ref007(module, declarations, path))
        out.extend(check_ref012(module, dependencies, workspace, path))
    return out


def check_seams(declarations, paths, manifest_deps, in_scope):
    """The door the honest-pre-commit gate reaches (§8): hand the inputs to
    run_seam_rules and return the combined diagnostics, holding no logic itself."""
    return run_seam_rules(declarations, paths, manifest_deps, in_scope)
