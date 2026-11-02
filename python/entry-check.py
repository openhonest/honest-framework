#!/usr/bin/env python
"""Every declared entry names a call site that exists.

An `entry "<callsite>" -> target` says who starts a function. Unchecked, it is a sentence: I wrote
`entry "import honest_parse" -> parse_source` to clear a red card about a function nothing starts,
and nothing imports parse_source, so the card was right and the declaration was not. An entry nobody
can check is worse than no entry, because the map reads it as the world arriving.

This checks the one callsite form the framework uses today. An import entry is true when some module
outside the declaring package imports that name from that package. Any other callsite form names the
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


def findings(declarations) -> list:
    out = []
    for package, module, entries, _roles in declarations:
        reached = imported_names(package)
        for entry in entries:
            callsite, target = entry["callsite"], entry["target"]
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
    the orchestrator calls the pure functions. An entry naming an orchestrator declares a door that
    is not there; an entry naming an output boundary declares the world starting an exit. Both are
    wrong arrivals and both still fail.

    An entry naming a pure function is a right arrival, not a missing door. A door exists to be the
    one place a module touches the world, so that contact is contained and checked; a pure function
    touches nothing, so there is nothing for a door to guard, and the world may call it directly.
    This holds whether or not the module has boundaries (ruling, 2026-11-01): a module with no
    boundary is a pure library, and a module that has boundaries may still publish pure functions for
    another program to import and call, as honest-check publishes its integration rules for the
    hd-check gate. The pure function's own completeness of contract, and its place in the call graph
    (reached from an orchestrator or another pure function), are checked by the map, not here; this
    rule asks only whether the world reached past a door it should have used. honest-parse once
    carried four functions imported straight out of its core (node_text, line_col, walk,
    first_error_node), which read as missing doors before that question was settled.
    """
    out = []
    for package, module, entries, roles in declarations:
        has_boundary = any(r in ("boundary_in", "reader", "boundary_out") for r in roles.values())
        for entry in entries:
            target, role = entry["target"], roles.get(entry["target"])
            # A pure library (no boundary) has nothing to guard, so every entry is a right arrival.
            if not has_boundary:
                continue
            # A pure function guards no world-contact, so the world may call it directly even where
            # the module has boundaries. Only an orchestrator (door missing) or an output boundary
            # (an exit the world should not start) is a wrong arrival.
            if role in (None, "boundary_in", "reader", "fn"):
                continue
            kind = ("an orchestrator, so the door the world should arrive at is missing"
                    if role == "orchestrator" else
                    "an output boundary, an exit the world should not start directly")
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
            if module["entries"]:
                roles = {f["name"]: f.get("role", "fn") for f in module["functions"]}
                declarations.append((path.parts[-2], module["name"], module["entries"], roles))
    problems = findings(declarations) + arrivals(declarations)
    counted = sum(len(entries) for _, _, entries, _ in declarations)
    # A host-loop entry (UNCHECKED: a callsite form that is not an import) names the program that runs
    # the framework from outside every module, so no import reaches it and the checker cannot read it.
    # It prints but does not fail the commit. A FALSE entry (an import nothing makes) and a NO DOOR
    # entry (the world landing on a non-boundary) are wrong, not merely unreadable, so they still fail.
    noted = [p for p in problems if p.strip().startswith("UNCHECKED")]
    failures = [p for p in problems if not p.strip().startswith("UNCHECKED")]
    for line in failures + noted:
        print(line, file=sys.stderr)
    print(f"entry-check: {counted} declared entr(ies) across {len(declarations)} declaration(s), "
          f"{len(failures)} wrong, {len(noted)} host-loop entr(ies) noted (not verified, not failed).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
