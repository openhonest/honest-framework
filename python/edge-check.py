#!/usr/bin/env python
"""The edge role is withdrawn. This is what ends its support rather than reminding somebody to.

Adam withdrew `edge` on 2026-11-14, against his own rule that a declared function justifies its
place three ways and no others: a boundary the world requires, an orchestrator joining at least
one boundary and at least one pure function, or a pure function that at least one orchestrator or
pure function calls. An edge satisfies none of them by construction, because "nothing inside the
module invokes it" was written into its definition, so the role named the exception rather than
repairing it. Named, it became the hiding place: a rule set written into an edge is reached by
whatever imports it, while every other check asks what the module calls or what the module
touches and so looks elsewhere.

The grammar still parses the word, because deleting it while declarations carry it would stop
every tree parsing in the same moment. So the support outlives the role for exactly as long as a
declaration needs it, and a temporary allowance with nothing to end it becomes permanent. This
script is the end. While an edge remains it warns and names what is left, module by module. On
the run where the last one goes it fails instead, printing every place the word is still wired in
and telling the reader to delete this script along with them.

Why a workspace script rather than the validator or the map. `validate` sees one module, and one
module holding no edge says nothing about the workspace. The architecture explorer renders the
declarations it was handed, and a subset holding no edge is not the same fact as the last edge
going, so letting a one-file render announce the retirement would make it noise and then make it
something people silence. Only a scan over every tree can tell the difference, so only a scan
makes the claim. Name the trees to scan; the default is this framework alone, which is not the
whole story while coolder carries copies.

    uv run --package honest-design python python/edge-check.py [tree ...]
"""

import pathlib
import sys

from honest_design import read_hd

EDGE_SITES = (
    "python/tree-sitter-honest-hd/grammar.js, the `role` choice",
    "python/honest-design/src/honest_design/reader.py, _ROLE_COLUMN",
    "python/honest-design/src/honest_design/validator.py, PURE_ROLES and _edge_role_withdrawn",
    "products/architecture-explorer/build-map.py, the ROLES table and the two role_of reads",
    "honest-check's HC-REF007, which accepts a seam onto a boundary_in or an edge",
    "specs/02-code-quality/honest-design-architecture.md and honest-check-architecture.md",
    "specs/rules.json and specs/features/honest-check.feature",
)


class EdgeRoleRetired(Exception):
    """Raised when no declaration uses `edge` any more, so the machinery that supports it can go.

    The role is withdrawn but the grammar still parses it, because deleting the word while 81
    declarations still carry it would stop every tree parsing in the same moment. So the support
    outlives the role on purpose, for exactly as long as a declaration needs it. It lives here
    rather than in honest-design, which reads `.hd` files and does nothing else: this is a fact
    about the state of a workspace, not about any declaration, and it raises where honest-design
    returns faults as data.

    A temporary allowance with nothing to end it becomes permanent, which is how `edge` lasted.
    This is the thing that ends it: while an edge remains the check warns and names what is left,
    and on the run where the last one goes it raises instead, naming every file still carrying
    the word. Nobody has to remember, and the reminder cannot be satisfied by ignoring it.
    """


def edge_retirement(modules):
    """Warn while any module still declares an edge; raise once none does.

    `modules` is every module IR in view. Only main below calls it, and only over the trees it
    was named, because no smaller view can tell a subset holding no edge from the last edge in
    the workspace going. Returns the warning text while edges remain; reaching zero raises.
    """
    carrying = [(m["name"], f["name"]) for m in modules
                for f in m["functions"] if f["role"] == "edge"]
    if not carrying:
        raise EdgeRoleRetired(
            "No declaration uses the edge role any more, so delete the machinery that supports "
            "it. Remove the word from: " + "; ".join(EDGE_SITES) + ". Then delete this script, "
            "which exists only to reach this moment. It reads the modules it was handed, so "
            "confirm it was handed every tree before acting on it"
        )
    by_module = {}
    for module_name, function_name in carrying:
        by_module.setdefault(module_name, []).append(function_name)
    where = ", ".join(f"{name} ({len(fns)})" for name, fns in sorted(by_module.items()))
    return (f"The edge role is withdrawn and {len(carrying)} declarations still use it: {where}. "
            "Each one belongs to whoever calls it: a utility module of its own when many modules "
            "import it, the importing module as a plain fn when one does, and nowhere at all "
            "when nothing reaches it. This warning becomes an exception on the run where the "
            "last edge goes, telling you to delete the grammar and the rest of the support")


DEFAULT_TREES = (pathlib.Path(__file__).resolve().parent.parent,)
SKIP = {".venv", "node_modules", ".git", "__pycache__"}


def declarations(trees: list) -> list:
    """Every `.hd` under the named trees, parsed, skipping what does not parse.

    A file that does not parse is honest-design's fault to report through its own reader, and
    this script would only repeat it. Silence here is the right answer because the question is
    narrow: which declarations still carry the word.
    """
    found = []
    for tree in trees:
        for path in sorted(pathlib.Path(tree).rglob("*.hd")):
            if SKIP & set(path.parts):
                continue
            document = read_hd(path.read_text(encoding="utf-8"))
            if "ok" in document:
                found.extend(document["ok"]["modules"])
    return found


def main(argv: list) -> int:
    trees = [pathlib.Path(a) for a in argv[1:]] or list(DEFAULT_TREES)
    missing = [t for t in trees if not t.is_dir()]
    for tree in missing:
        print(f"edge-check: no such tree: {tree}", file=sys.stderr)
    if missing:
        return 2
    modules = declarations(trees)
    scanned = ", ".join(str(t) for t in trees)
    if not modules:
        print(f"edge-check: no declaration parsed under {scanned}, so nothing was judged. "
              "A scan that reads nothing must not report the role retired.", file=sys.stderr)
        return 2
    try:
        print(f"edge-check: {edge_retirement(modules)}", file=sys.stderr)
    except EdgeRoleRetired as retired:
        print(f"edge-check: {retired}", file=sys.stderr)
        print(f"edge-check: scanned {len(modules)} module(s) under {scanned}.", file=sys.stderr)
        return 1
    print(f"edge-check: scanned {len(modules)} module(s) under {scanned}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
