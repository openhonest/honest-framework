"""Which workspace members must carry a `.hd`, and which are exempt (HC-REF011, spec section 8).

A module that carries a package manifest but no declaration escapes every rule in the
declaration tier by being invisible, so the gate it would face is one you leave by deleting a
file. `undeclared_members` names those modules. `membership-check.py` walks the workspace at
the boundary and hands this the two sets, the members it found and those found to carry a
declaration, and the difference is the finding.

**Absence is not permission.** A workspace member carrying no `.hd` is a finding unless it is
exempt by name, with its reason written beside it. An exemption is a decision somebody made
and can be argued with; a missing file is neither. The reason is the whole point of the table,
so an entry is never left empty.
"""

# Workspace members that carry no `.hd`, each with the reason it does not. An exemption is a
# decision somebody made and can be argued with; a missing file is neither.
EXEMPT_FROM_DECLARATION = {
    "tree-sitter-honest-hd": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "tree-sitter-honest-jinja": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "honest-boot": "declaration owed: 14 exports, each needing a role a person assigns. Inferring boundary from a watch-list would infer what the framework says must be declared. Tracked as honest-framework-jb7",
    "honest-dom": "declaration owed: 27 exports, same reason as honest-boot. Tracked as honest-framework-jb7",
    "honest-components": "declaration owed and blocked: it already declares its behaviour vocabulary in manifest.json, which honest-check reads for HC-REF004, so a .hd added now would be a second copy. Blocked on whether the manifest becomes generated or disappears. Tracked as honest-framework-jb7",
    "honest-format": "declaration owed and blocked: same manifest.json conflict as honest-components. Tracked as honest-framework-jb7",
}


def undeclared_members(members, with_declaration):
    """Workspace members that carry no `.hd` and no exemption, sorted.

    `members` is what the workspace was found to contain and `with_declaration` is what was
    found to carry a declaration; the difference, minus the exempt members, is the finding. An
    exempt member is subtracted by name, never by noticing its file is missing.
    """
    return sorted(set(members) - set(with_declaration) - set(EXEMPT_FROM_DECLARATION))
