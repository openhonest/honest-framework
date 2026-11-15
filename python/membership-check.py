"""Every module in the workspace declares itself, or is exempt by name with a reason.

A gate you can leave by deleting a file is not a gate, so this runs before anything looks at
the content of a declaration. Reading only the Python tree is how four JavaScript modules
stayed invisible to it: the declaration language is independent of the language a module is
written in, so the membership check has to be too.

Run from python/ by check-all.sh. The directory walk is the I/O; the decision is the pure
undeclared_members below, which takes two sets. It lives here, with its only caller, rather
than in honest-check: honest-check's own rules never call it, so it earned no place there.
"""

import pathlib
import sys

# A module is a directory carrying its language's package manifest.
MANIFESTS = ("pyproject.toml", "package.json")

# A member is exempt only by name, with the reason it is not yet declared; the list only
# shrinks (HC-REF011). A module absent from this table owes a declaration.
EXEMPT_FROM_DECLARATION = {
    "tree-sitter-honest-hd": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "tree-sitter-honest-jinja": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "honest-boot": "declaration owed: 14 exports, each needing a role a person assigns. Inferring boundary from a watch-list would infer what the framework says must be declared. Tracked as honest-framework-jb7",
    "honest-dom": "declaration owed: 27 exports, same reason as honest-boot. Tracked as honest-framework-jb7",
    "honest-components": "declaration owed and blocked: it already declares its behaviour vocabulary in manifest.json, which honest-check reads for HC-REF004, so a .hd added now would be a second copy. Blocked on whether the manifest becomes generated or disappears. Tracked as honest-framework-jb7",
    "honest-format": "declaration owed and blocked: same manifest.json conflict as honest-components. Tracked as honest-framework-jb7",
}


def undeclared_members(members, with_declaration):
    """Workspace members that carry no .hd and no exemption, sorted. Pure: the directory walk
    is the boundary in main(); this is the decision. An exempt member is subtracted by name,
    never by noticing its file is missing."""
    return sorted(set(members) - set(with_declaration) - set(EXEMPT_FROM_DECLARATION))


def modules(roots):
    """Every module directory under the given trees. I/O: this is the boundary."""
    return [d for root in roots if root.is_dir() for d in root.iterdir()
            if d.is_dir() and any((d / m).exists() for m in MANIFESTS)]


def main():
    # cwd, not Path("."): the parent of a relative "." is "." again, so a relative root never
    # leaves the tree it started in and the check passes having looked at nothing.
    here = pathlib.Path.cwd()
    found_modules = modules([here, here.parent / "javascript"])
    missing = undeclared_members(
        {d.name for d in found_modules},
        {d.name for d in found_modules if list(d.glob("*.hd"))},
    )
    if not missing:
        return 0
    print("HC-REF011: these modules carry no .hd and no exemption, so they escape every "
          "declaration check: " + ", ".join(missing), file=sys.stderr)
    print("  Write the declaration, or add the module to EXEMPT_FROM_DECLARATION with its reason.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
