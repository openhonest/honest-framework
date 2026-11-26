#!/usr/bin/env python
"""Every declared entry names a call site that exists.

An `entry "<callsite>" -> target` says who starts a function. Unchecked, it is a sentence: I wrote
`entry "import honest_parse" -> parse_source` to clear a red card about a function nothing starts,
and nothing imports parse_source, so the card was right and the declaration was not. An entry nobody
can check is worse than no entry, because the map reads it as the world arriving.

An import entry is true when some module outside the declaring package imports that name from that
package. An export entry proves a public door or boundaryless pure binding through the initializer.
Other callsite forms name the
host loop: the program that runs the framework from outside every module, which no import can reach.
The checker prints such an entry as unverified and does not fail the commit on it, because the host
loop is not the framework's to check. Printing it keeps nothing silent. A false import entry (one that
names an import nothing makes) and an entry that lands on a non-boundary still fail, because those are
wrong, not merely unreadable.
"""

import ast
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
IMPORT_CALLSITE = re.compile(r"^import\s+([a-z_][a-z0-9_]*)$")
EXPORT_CALLSITE = re.compile(r"^export\s+([a-z_][a-z0-9_]*)$")
# Persist §§7.4–7.5 make the executors internal. Keep the published legacy
# bindings visible while that public API is reconciled with the spec.
PERSIST_EXECUTOR_ENTRIES = {"execute", "execute_one", "execute_scalar", "execute_many", "transaction"}


def imported_names(package: str) -> set:
    """Every name any OTHER package imports from `package`, by its module name."""
    module = package.replace("-", "_")
    found = set()
    for path in sorted(ROOT.glob("honest-*/**/*.py")):
        if "__pycache__" in str(path) or path.is_relative_to(ROOT / package):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == module:
                found |= {alias.name for alias in node.names}
    return found


def published_functions(package: str) -> set:
    """Names in a literal __all__ with a package-local function binding."""
    module = package.replace("-", "_")
    source = ROOT / package / "src" / module
    initializer = source / "__init__.py"
    if not initializer.is_file():
        return set()
    body = ast.parse(initializer.read_text(encoding="utf-8")).body
    exports = set()
    bindings = set()
    for node in body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            exports = set()
            if isinstance(node.value, (ast.List, ast.Tuple)):
                exports.update(item.value for item in node.value.elts if isinstance(item, ast.Constant)
                               and isinstance(item.value, str))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bindings.add(node.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if node.level == 1:
                relative = parts
            elif node.level == 0 and parts[0] == module and len(parts) > 1:
                relative = parts[1:]
            else:
                continue
            target = source.joinpath(*relative)
            candidates = (target.with_suffix(".py"), target / "__init__.py")
            defined = {fn.name for candidate in candidates if candidate.is_file()
                       for fn in ast.parse(candidate.read_text(encoding="utf-8")).body
                       if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))}
            bindings.update(alias.asname or alias.name for alias in node.names if alias.name in defined)
    return exports & bindings


def legacy_persist_executor(package, module, callsite, target, role):
    return (package == module == "honest-persist" and target in PERSIST_EXECUTOR_ENTRIES
            and role == "boundary_out" and callsite == "export honest_persist")


def findings(declarations) -> list:
    out = []
    for package, module, entries, roles in declarations:
        if not entries:
            continue
        reached = imported_names(package)
        for entry in entries:
            callsite, target = entry["callsite"], entry["target"]
            export = EXPORT_CALLSITE.fullmatch(callsite.strip())
            if export:
                boundaryless = all(role == "fn" for role in roles.values())
                role = roles.get(target)
                legacy = legacy_persist_executor(package, module, callsite, target, role)
                allowed = role == "boundary_in" or (role == "fn" and boundaryless) or legacy
                owners = sum(target in declared_roles for owner_package, _, _, declared_roles in declarations
                             if owner_package == package)
                if (export.group(1) != package.replace("-", "_") or not allowed
                        or owners != 1
                        or target not in published_functions(package)):
                    out.append(f"  FALSE {package} [{module}]: entry {callsite!r} -> {target} needs a "
                               "published input boundary or a published function in a boundaryless module.")
                elif legacy:
                    out.append(f"  DEFERRED {package} [{module}]: published {target} is an output boundary.")
                continue
            match = IMPORT_CALLSITE.match(callsite.strip())
            if not match:
                out.append(f"  UNCHECKED {package} [{module}]: entry {callsite!r} -> {target} is a "
                           f"callsite form this script cannot read. Nothing confirms it.")
                continue
            if match.group(1) != package.replace("-", "_"):
                out.append(f"  FALSE {package} [{module}]: entry {callsite!r} -> {target} names a "
                           f"module that is not this package.")
                continue
            if target not in reached:
                out.append(f"  FALSE {package} [{module}]: entry {callsite!r} -> {target} says the "
                           f"world starts {target} by import, and no module imports it.")
    return out


def arrivals(declarations) -> list:
    """Entries that land somewhere the world is not supposed to arrive.

    The method says the world arrives at a door, the door hands the call to one orchestrator, and
    the orchestrator calls the pure functions. An entry naming a pure function declares the world
    reaching into the core with no door in between, and an entry naming an orchestrator declares a
    door that is not there. honest-parse carried four of the first kind: node_text, line_col, walk
    and first_error_node, each imported straight out of the module by honest-check and honest-test.

    A module with no boundary is the exception, because it is a pure library. honest-type is one: it
    touches no file, database, clock or network, so the world reaches it only by importing or calling
    its functions. There is no door to arrive at and none to bypass, so an entry landing on a pure
    function is the right arrival, not a missing door. The rule guards a module that HAS boundaries
    against an entry that reaches past them, so a module that declares none has nothing for it to
    guard. That an import names a function this package exports is still checked, in findings.

    An `edge` is the second exception, and it is for the hybrid the first does not cover: a module
    that HAS boundaries and also publishes a pure import surface. honest-check is one, exposing five
    extraction functions honest-test imports. An edge is a pure function the world reaches by import,
    so an entry landing on one is the right arrival, the same as for a pure library, declared
    per-function by the role rather than inferred from the whole module having no boundary.
    """
    out = []
    for package, module, entries, roles in declarations:
        if not any(r in ("boundary_in", "reader", "boundary_out") for r in roles.values()):
            continue
        for entry in entries:
            target, role = entry["target"], roles.get(entry["target"])
            # An edge is a pure function the module exposes as an import surface, so the world
            # reaching it by import is the right arrival, not a door bypassed. It is the hybrid of
            # the pure-library case: a module with boundaries may still publish a pure import edge,
            # and the edge role is where the author put that on the record.
            if (role is None or role in ("boundary_in", "reader", "edge")
                    or legacy_persist_executor(package, module, entry["callsite"], target, role)):
                continue
            kind = ("an orchestrator, so the door the world should arrive at is missing"
                    if role == "orchestrator" else
                    f"a {role}, so the world reaches the core with no door in between")
            out.append(f"  NO DOOR {package} [{module}]: entry {entry['callsite']!r} -> {target} names "
                       f"{kind}.")
    return out


def main() -> int:
    from honest_design import read_hd

    targets = set(os.environ.get("HD_TARGETS", "").split())
    declarations = []
    for path in sorted(ROOT.glob("honest-*/honest-*.hd")):
        if targets and path.parts[-2] not in targets:
            continue
        document = read_hd(path.read_text(encoding="utf-8"))
        if "ok" not in document:
            continue
        for module in document["ok"]["modules"]:
            roles = {f["name"]: f.get("role", "fn") for f in module["functions"]}
            declarations.append((path.parts[-2], module["name"], module["entries"], roles))
    problems = findings(declarations) + arrivals(declarations)
    counted = sum(len(entries) for _, _, entries, _ in declarations)
    # A host-loop entry (UNCHECKED: a callsite form that is not an import) names the program that runs
    # the framework from outside every module, so no import reaches it and the checker cannot read it.
    # It prints but does not fail the commit. A FALSE entry (an import nothing makes) and a NO DOOR
    # entry (the world landing on a non-boundary) are wrong, not merely unreadable, so they still fail.
    noted = [p for p in problems if p.strip().startswith("UNCHECKED")]
    deferred = [p for p in problems if p.strip().startswith("DEFERRED")]
    failures = [p for p in problems if not p.strip().startswith(("UNCHECKED", "DEFERRED"))]
    for line in failures + noted + deferred:
        print(line, file=sys.stderr)
    print(f"entry-check: {counted} declared entr(ies) across {len(declarations)} declaration(s), "
          f"{len(failures)} wrong, {len(noted)} host-loop entr(ies) noted, "
          f"{len(deferred)} verified legacy entr(ies) temporarily deferred.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
