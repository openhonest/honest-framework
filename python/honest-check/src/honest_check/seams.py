"""The cross-module seam checks (§8, §HC-REF006/§HC-REF007/§HC-REF012). The gate
loads every module's parsed declaration and reaches one door, check_seams, which
runs the three cross-module rules over the in-scope modules. The rules are pure: a
declaration arrives already parsed, so nothing here opens a file."""

import re
from pathlib import Path

from ._util import choose, pick, read_or


# The closed world-token vocabulary: a bare side-effect target naming one of these
# (or carrying a ':' env marker, or written all-uppercase) names the world, not a
# module. honest-design leaves a bare module target's `module` field empty, so a
# bare module name is told from a world token here rather than by that field alone.
_WORLD_TOKENS = {
    "DOM", "HTTP", "HTTPS", "file", "stdin", "stdout", "stderr", "clock", "random",
    "time", "network", "env", "argv", "process",
}


# inherits: hd=python/honest-check/honest-check.hd::_is_world -> feature=specs/features/honest-check.feature::_is_world identifies recognized world and resource targets -> test=python/honest-check/conformance/probe_parsed_seams_is_world.py::probe_parsed_seams_is_world
# hd: _is_world
def _is_world(target):
    return bool(target in _WORLD_TOKENS or ":" in target or target.isupper())


# inherits: hd=python/honest-check/honest-check.hd::_bare_seam -> feature=specs/features/honest-check.feature::_bare_seam keeps only a standalone bare module target -> test=python/honest-check/conformance/probe_parsed_seams_bare_seam.py::probe_parsed_seams_bare_seam
# hd: _bare_seam
def _bare_seam(caller, effect):
    target = effect["target"]
    return pick(
        _is_world(target) or re.fullmatch(_HD_IDENTIFIER, target) is None,
        lambda: [],
        lambda: [{"caller": caller, "module": target, "door": "", "direction": effect["direction"]}],
    )


# inherits: hd=python/honest-check/honest-check.hd::_seam_of -> feature=specs/features/honest-check.feature::_seam_of preserves a qualified seam and skips an empty target -> test=python/honest-check/conformance/probe_parsed_seams_seam_of.py::probe_parsed_seams_seam_of
# hd: _seam_of
def _seam_of(caller, effect):
    return pick(
        effect["target"] != "" and effect["module"] != "",
        lambda: [
            {"caller": caller, "module": effect["module"], "door": effect["door"], "direction": effect["direction"]}
        ],
        lambda: _bare_seam(caller, effect),
    )


# inherits: hd=python/honest-check/honest-check.hd::declared_seams -> feature=specs/features/honest-check.feature::declared_seams -> test=python/honest-check/conformance/probe_parsed_seams_declared_seams.py::probe_parsed_seams_declared_seams
# hd: declared_seams
def declared_seams(module):
    """Every cross-module seam one module declares — one per side effect whose target
    names another module; a world-named side effect is skipped (§8). A bare module
    target (whose declaration-parsed `module` field is empty) is kept when it names
    a module and is not a world token."""
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


_HD_IDENTIFIER = r"[a-zA-Z_][a-zA-Z0-9_]*(?:-[a-zA-Z0-9_]+)*"
_PURE_CALL_TARGET = re.compile(rf"{_HD_IDENTIFIER}\.{_HD_IDENTIFIER}")


# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns invalid_role for impure targets -> test=python/honest-check/conformance/probe_resolve_pure_calls_impure.py::probe_resolve_pure_calls_impure
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns unresolved for malformed targets -> test=python/honest-check/conformance/probe_resolve_pure_calls_malformed.py::probe_resolve_pure_calls_malformed
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns unresolved for missing targets -> test=python/honest-check/conformance/probe_resolve_pure_calls_missing.py::probe_resolve_pure_calls_missing
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls preserves resolved occurrences in declaration order -> test=python/honest-check/conformance/probe_resolve_pure_calls_ordered.py::probe_resolve_pure_calls_ordered
# hd: resolve_pure_calls
def resolve_pure_calls(module, declarations):
    """Resolve each authored pure call without introducing an I/O seam."""
    resolutions = []
    for caller in module["functions"]:
        for target in read_or(caller, "pure_calls", []):
            target_module, _, target_name = target.partition(".")
            qualified = _PURE_CALL_TARGET.fullmatch(target) is not None
            target_module = choose(qualified, target_module, "")
            declaration = read_or(declarations, target_module, None)
            functions = pick(
                qualified and target_module != module["name"] and declaration is not None,
                lambda: declaration["functions"],
                lambda: [],
            )
            callee = next(filter(lambda function: function["name"] == target_name, functions), None)
            pure = (
                callee is not None
                and not read_or(callee, "side_effects", [])
                and all(function["role"] == "fn" for function in functions)
            )
            status = choose(callee is None, "unresolved", choose(pure, "resolved", "invalid_role"))
            resolutions.append({
                "caller": caller["name"],
                "target": target,
                "module": target_module,
                "status": status,
            })
    return resolutions


# inherits: hd=python/honest-check/honest-check.hd::pure_call_findings -> feature=specs/features/honest-check.feature::pure_call_findings reports ordered errors at the caller declaration path -> test=python/honest-check/conformance/probe_pure_call_findings_ordered.py::probe_pure_call_findings_ordered
# hd: pure_call_findings
def pure_call_findings(calls, path):
    """Report every failed pure call in annotation order at its declaration."""
    findings = []
    for call in filter(lambda call: call["status"] != "resolved", calls):
        rule, problem = choose(
            call["status"] == "unresolved",
            ("HC-REF006", "does not resolve to a declared function in another module"),
            ("HC-REF007", "must target a plain function without side effects in a boundaryless module"),
        )
        findings.append(_seam_diagnostic(rule, path, f"{call['caller']}: pure_call {call['target']!r} {problem}"))
    return findings


# inherits: hd=python/honest-check/honest-check.hd::distribution_pure_dependencies -> feature=specs/features/honest-check.feature::distribution_pure_dependencies includes only resolved calls from the caller distribution -> test=python/honest-check/conformance/probe_distribution_pure_dependencies_resolved.py::probe_distribution_pure_dependencies_resolved
# hd: distribution_pure_dependencies
def distribution_pure_dependencies(module_name, paths, calls_by_module):
    """Collect resolved target modules from declarations in the owner's manifest directory."""
    owner_path = read_or(paths, module_name, "")
    directory = Path(owner_path).parent
    members = filter(
        lambda member: owner_path and member[1] and Path(member[1]).parent == directory,
        paths.items(),
    )
    return {
        call["module"]
        for name, _ in members
        for call in filter(
            lambda call: call["status"] == "resolved", read_or(calls_by_module, name, [])
        )
    }


# inherits: hd=python/honest-check/honest-check.hd::run_seam_rules -> feature=specs/features/honest-check.feature::run_seam_rules checks scoped pure calls alongside I/O seams -> test=python/honest-check/conformance/probe_run_seam_rules_scoped_pure_calls.py::probe_run_seam_rules_scoped_pure_calls
# hd: run_seam_rules
def run_seam_rules(declarations, paths, manifest_deps, in_scope):
    """Resolve against the full workspace and report findings for the selected modules."""
    scope = choose(len(in_scope) == 0, list(declarations.keys()), in_scope)
    workspace = list(declarations.keys())
    calls_by_module = {
        name: resolve_pure_calls(module, declarations) for name, module in declarations.items()
    }
    out = []
    for name in scope:
        module = declarations[name]
        path = read_or(paths, name, "")
        dependencies = read_or(manifest_deps, name, [])
        pure_dependencies = distribution_pure_dependencies(name, paths, calls_by_module)
        dependencies_without_pure_evidence = list(
            filter(lambda dependency: dependency not in pure_dependencies, dependencies)
        )
        out.extend(check_hc_ref006(module, declarations, path))
        out.extend(check_hc_ref007(module, declarations, path))
        out.extend(pure_call_findings(calls_by_module[name], path))
        out.extend(check_ref012(module, dependencies_without_pure_evidence, workspace, path))
    return out


def check_seams(declarations, paths, manifest_deps, in_scope):
    """The door the honest-pre-commit gate reaches (§8): hand the inputs to
    run_seam_rules and return the combined diagnostics, holding no logic itself."""
    return run_seam_rules(declarations, paths, manifest_deps, in_scope)
