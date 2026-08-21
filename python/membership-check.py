"""Every module in the workspace declares itself, or is exempt by name with a reason.

A gate you can leave by deleting a file is not a gate, so this runs before anything looks at
the content of a declaration. Reading only the Python tree is how four JavaScript modules
stayed invisible to it: the declaration language is independent of the language a module is
written in, so the membership check has to be too.

Run from python/ by lint-all.sh. The directory walk is the I/O; the decision is
honest_check.declared.undeclared_members, which is pure and takes two sets.
"""

import pathlib
import sys

from honest_check.declared import undeclared_members

# A module is a directory carrying its language's package manifest.
MANIFESTS = ("pyproject.toml", "package.json")


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
    print("lint-all: these modules carry no .hd and no exemption: " + ", ".join(missing), file=sys.stderr)
    print("  Write the declaration, or add the module to EXEMPT_FROM_DECLARATION with its reason.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
