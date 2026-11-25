#!/usr/bin/env bash
# The .hd dogfood gate: every framework module's own .hd declaration must parse (read_hd -> ok) and
# validate clean (validate -> []). As modules are declared in .hd, this keeps those declarations
# honest — checked by honest-design's own read path.
set -uo pipefail
cd "$(dirname "$0")"

# Affected-only, like every other gate. With module arguments, each check below is restricted to
# those modules; with none, the whole framework is swept (bootstrap, a manual run, CI). The commit
# hook passes the modules whose .hd or source is staged, so one module's declaration debt stops
# blocking a commit that never touches it. Cross-module checks (the seams) still load every
# declaration to resolve a caller's named door, but report only against the modules in scope.
HD_TARGETS="$*"
export HD_TARGETS
in_scope() { [ -z "$HD_TARGETS" ] && return 0; case " $HD_TARGETS " in *" $1 "*) return 0;; *) return 1;; esac; }

# Every module with source carries an .hd. "ALL CODE MUST START WITH AN .hd FILE" has no teeth if the
# declaration checks below only run on the .hd files that happen to exist: a module with src/ and no
# .hd ever written passes every check by never triggering one — the silent-miss gap P16 names, a miss
# filed as a hit because nothing looks for the miss. Adapted from the commercial track's gate
# (commercial-honest/.githooks/pre-commit §2a), scoped here to the framework's own src layout.
missing_hd=0
shopt -s nullglob
for src in honest-*/src/honest_*; do
    [ -d "$src" ] || continue
    pkg=${src%%/src/*}
    in_scope "$pkg" || continue
    if [ ! -f "$pkg/$pkg.hd" ]; then
        missing_hd=1
        echo "  NO .hd  $pkg has $src but no $pkg/$pkg.hd — code without a declaration is undeclared by construction."
    fi
done
echo "honest-pre-commit: module-declaration existence — $([ "$missing_hd" -eq 0 ] && echo 'every module with src/ carries its .hd' || echo "$missing_hd module(s) have src/ and no .hd")."
echo ""

uv run --package honest-design python - <<'PY'
import glob, os, sys
from honest_design import read_hd, validate
targets = set(os.environ.get("HD_TARGETS", "").split())
files = [f for f in sorted(glob.glob("honest-*/honest-*.hd"))
         if not targets or f.split("/")[0] in targets]
bad = 0
for path in files:
    doc = read_hd(open(path).read())
    if "err" in doc:
        bad += 1
        print(f"  PARSE   {path}: {doc['err']['message']}")
        continue
    for module in doc["ok"]["modules"]:
        for fault in validate(module):
            bad += 1
            print(f"  INVALID {path} [{module['name']}]: {fault['code']} — {fault['message']}")
print(f"honest-pre-commit: {len(files)} .hd declaration(s), {bad} problem(s)")
sys.exit(1 if bad else 0)
PY
status=$(( $? || missing_hd ))

# The seams. A caller names the callee's door on its own side effect, with a dot, and resolving it
# needs both declarations in view, which is why it runs here rather than in the validator. A module
# not among the sixteen is skipped rather than reported dead: a gate whose answer changes with how
# it was invoked is not a gate.
echo ""
uv run --package honest-check python - <<'PY'
import glob, os, re, sys, tomllib
from pathlib import Path
from honest_design import read_hd
from honest_check import check_seams

targets = set(os.environ.get("HD_TARGETS", "").split())
declarations = {}
paths = {}
manifest_deps = {}
for path in sorted(glob.glob("honest-*/honest-*.hd")):
    document = read_hd(Path(path).read_text(encoding="utf-8"))
    if "ok" not in document:
        continue
    manifest = Path(path).with_name("pyproject.toml")
    project = {}
    dependencies = []
    if manifest.is_file():
        project = tomllib.loads(manifest.read_text(encoding="utf-8")).get("project", {})
        dependencies = [
            re.sub(r"[-_.]+", "-", match[0]).lower()
            for requirement in project.get("dependencies", [])
            if (match := re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.lstrip()))
        ]
    for module in document["ok"]["modules"]:
        name = module["name"]
        declarations[name] = module
        paths[name] = path
        # Dependencies belong to the distribution declared by the manifest.
        # A separately declared module inside that distribution does not inherit them.
        manifest_deps[name] = dependencies if name == project.get("name") else []

# Resolve against the whole workspace and report findings for affected modules.
in_scope = sorted(name for name in declarations if not targets or paths[name].split("/")[0] in targets)
findings = check_seams(declarations, paths, manifest_deps, in_scope)
for d in findings:
    print(f"  {d['rule_id']} {d['source_location']}: {d['message']}")
print(f"honest-pre-commit: cross-module seams checked across {len(declarations)} declaration(s), "
      f"{len(findings)} unresolved.")
sys.exit(1 if findings else 0)
PY
status=$(( status || $? ))

# Entries: a declaration says who starts a function, and an entry nobody can check is a sentence
# rather than a declaration. The map reads declarations only, so it cannot know what any module
# imports; crossing the declaration with the code is this gate's job. Written after I declared
# `entry "import honest_parse" -> parse_source` to clear a red card about a function nothing
# starts. Nothing imported it, the card was right, and the declaration was not.
echo ""
if ! uv run --package honest-design python entry-check.py; then
    status=1
fi
# The declaration crossed with the code: HC-R002 (an output boundary calling inward) and HC-R003 (the
# declaration and the async keyword disagreeing about awaiting) read each package's own .hd against its
# source. Only these two rules here; the rest of honest-check runs in check-affected.sh.
for hd in honest-*/honest-*.hd; do
    pkg=${hd%%/*}
    [ -d "$pkg/src" ] || continue
    in_scope "$pkg" || continue
    out=$(uv run --package honest-check python -m honest_check.cli --declaration "$hd" --rule HC-R002 --rule HC-R003 --rule HC-R004 --rule HC-R005 "$pkg/src" 2>&1) || { status=1; printf '%s\n' "$out"; }
done

# HC-REF005 crosses the same declaration with the package's own export list: an exported function no
# .hd names, or a declared parameter count that disagrees with the code. It is one-directional — the
# build order writes the .hd first, so a declared function the code has not written yet is the allowed
# lag and is not a finding. It needs the export list as well as the declaration, so it runs per package
# here rather than beside the two above.
#
# NOT_CROSSED names the packages whose declaration and code do not yet agree, each with its count read
# on 2026-10-02. A package absent from this list is gated. A package on it is on the record as ungated,
# which is the difference between a backlog and a silence. The list only shrinks: a package comes off
# it when the change that next touches it brings its .hd into agreement, because the order of work is
# spec, declaration, failing test, code. Removing an entry is how a package becomes gated; adding one
# is not a repair.
NOT_CROSSED="honest-observe honest-persist honest-alerts honest-auth honest-errors honest-gherkin honest-rca honest-type honest-page honest-test"
uv run --package honest-check python - "$NOT_CROSSED" <<'PY'
import os
from pathlib import Path
import sys

from honest_check import cross_declaration, pair_source, read_source
from honest_design import read_hd

exempt = set(sys.argv[1].split())
targets = set(os.environ["HD_TARGETS"].split())
failed = False
checked = 0
for package in sorted(Path.cwd().glob("honest-*")):
    name = package.name
    source_dir = package / "src"
    if name in exempt or (targets and name not in targets) or not source_dir.is_dir():
        continue
    paths = sorted(package.glob("honest-*.hd"))
    if not paths:
        continue
    exports = source_dir / name.replace("-", "_") / "__init__.py"
    if not exports.is_file():
        print(f"  honest-pre-commit: {name} is gated for HC-REF005 and has no {exports}")
        failed = True
        continue
    functions = []
    for path in paths:
        document = read_hd(path.read_text(encoding="utf-8"))
        if "err" in document:
            print(f"  honest-pre-commit: cannot read {path}: {document['err']['message']}")
            failed = True
            continue
        for module in document["ok"]["modules"]:
            functions.extend(module["functions"])
    files = sorted(source_dir.rglob("*.py"))
    sources = [pair_source(str(path), read_source(str(path))) for path in files]
    diagnostics = cross_declaration(
        sources, {"functions": functions}, read_source(str(exports)), ["HC-REF005"]
    )
    for finding in diagnostics:
        print(f"{finding['source_location']}: {finding['rule_id']} {finding['message']}")
    failed |= bool(diagnostics)
    checked += 1
print(f"honest-pre-commit: HC-REF005 checked {checked} package(s); {len(exempt)} still to cross.")
sys.exit(int(failed))
PY
status=$(( status || $? ))

# Every exported function must be reachable by the world, through the declaration alone: it is the
# target of an entry or a route, or something reachable from one calls it. A function the world
# cannot reach is surface the declaration cannot account for, and the opposite case is worse: a
# declaration that lists functions and never says how any of them is started describes a module
# nothing can run. Fifteen of the sixteen declarations were in that state on 2026-10-02, and the
# map reported it as 200 red cards while every gate here passed.
#
# Checked only for the packages HC-REF005 gates, for the same reason: a package whose declaration
# and code have not been crossed yet has nothing to be reachable against.
echo ""
uv run --package honest-design python - "$NOT_CROSSED" <<'PY'
import ast, glob, os, sys
from honest_design import read_hd

not_crossed = set(sys.argv[1].split())
targets = set(os.environ.get("HD_TARGETS", "").split())
bad = 0
checked = 0
for path in sorted(glob.glob("honest-*/honest-*.hd")):
    package = path.split("/")[0]
    if package in not_crossed:
        continue
    if targets and package not in targets:
        continue
    init = f"{package}/src/{package.replace('-', '_')}/__init__.py"
    try:
        tree = ast.parse(open(init).read())
    except OSError:
        continue
    exported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "__all__" for t in node.targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                exported = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    document = read_hd(open(path).read())
    if "ok" not in document:
        continue
    for module in document["ok"]["modules"]:
        functions = {f["name"]: f for f in module["functions"]}
        # A function starts another two declared ways: by invoking it, and by chaining to it. A
        # chain `a -> b` says a hands its call to b, so a function the world reaches through a door
        # carries the rest of its chain with it. Following invokes alone left a door-to-orchestrator
        # chain looking unstarted, which flagged honest-parse's whole pure core as unreachable though
        # the door parse_source chains to place_source, which invokes the core.
        starts = {name: set(f.get("invokes") or []) for name, f in functions.items()}
        for chain in module.get("chains") or []:
            links = chain.get("links") or []
            for caller, callee in zip(links, links[1:]):
                starts.setdefault(caller, set()).add(callee)
        # A function starts another a third declared way: by dispatching to it. A dispatch
        # `d = { "k" -> h }` that a function invokes hands that function's call to a handler, so
        # every handler is started by whoever invokes the dispatch. The dispatch name carries its
        # handlers in `starts`, so a function that invokes the dispatch reaches them. Following
        # invokes and chains alone left honest-check's four format_* renderers, reached only through
        # the by_format dispatch run_check invokes, looking unstarted, which the explorer map did not.
        for dispatch in module.get("dispatches") or []:
            handlers = {entry["handler"] for entry in (dispatch.get("entries") or [])}
            starts.setdefault(dispatch["name"], set()).update(handlers)
        reached = {e["target"] for e in module["entries"]} | {r["target"] for r in module.get("routes") or []}
        frontier = set(reached)
        while frontier:
            frontier = {c for name in frontier for c in starts.get(name, ())} - reached
            reached |= frontier
        unreachable = sorted(n for n in exported & set(functions) if n not in reached)
        checked += 1
        for name in unreachable:
            bad += 1
            print(f"  UNREACHABLE {package} [{module['name']}]: '{name}' is exported and no entry, route "
                  f"or declared call reaches it. Declare who starts it.")
print(f"honest-pre-commit: world-reachability checked on {checked} declaration(s), {bad} unreachable export(s).")
sys.exit(1 if bad else 0)
PY
status=$(( status || $? ))
exit $status
