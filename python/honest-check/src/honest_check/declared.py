"""The declared roles a module's `.hd` carries, and which members must carry one.

honest-check reconstructed a function's role from its Python decorator, and
`link(boundary=False)` carries one boolean. The declaration is richer: it separates
`boundary_in` from `boundary_out` and names the resource each one touches. So the gate
enforced a coarser role than the author wrote down, and no rule about the direction of the
arrows between columns could be stated from Python alone (honest-design section 3.1).

The `.hd` is read through honest-design, which owns the format. Parsing it a second time here
would put one fact in two places, which is the drift this module exists to catch.

**Absence is not permission.** A declaration that would not parse and a declaration of nothing
are different facts, so they are different values: one is a named failure, the other is an
empty mapping. Collapsing them into a single empty result is how a gate comes to be satisfied
by deleting the file it reads, which is no gate at all. For the same reason membership is
declared: a workspace member carrying no `.hd` is a finding unless it is exempt by name, with
its reason written beside it.
"""

from honest_design.result import err, fault, ok
from honest_design.reader import read_hd

# A function's column in the four-column model, keyed by the role keyword the author wrote.
# Read by subscript from a closed set: a keyword absent from it is a grammar change nobody
# taught this module about, and it must surface rather than resolve to a default column.
COLUMNS = {"boundary_in": 1, "orchestrator": 2, "fn": 3, "boundary_out": 4}

# Workspace members that carry no `.hd`, each with the reason it does not. An exemption is a
# decision somebody made and can be argued with; a missing file is neither. The reason is the
# whole point of the table, so an entry with an empty one fails the law that reads it.
EXEMPT_FROM_DECLARATION = {
    "tree-sitter-honest-hd": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "tree-sitter-honest-jinja": "a tree-sitter grammar package: generated C and a grammar.js, no honest functions to declare",
    "honest-page": "declaration blocked, not waived: its contract is six rendered surfaces in a normative document order (spec 2.2), and the .hd language declares no surface and no ordering, so the file cannot be written without new syntax. Language gap is honest-framework-9ri, the declaration is honest-framework-3h1; remove this entry when the .hd lands",
}


def declared_roles(source):
    """Map each function name in `.hd` source to the role keyword its author declared.

    Returns ok(mapping) for source that parses, and err(fault) for source that does not, so a
    caller can tell a declaration of nothing from a declaration it could not read.
    """
    document = read_hd(source)
    if "ok" not in document:
        return err(fault("hd_unreadable", "the .hd source could not be read, so its roles are unknown", "client", {}))
    return ok({
        function["name"]: function["role"]
        for module in document["ok"]["modules"]
        for function in module["functions"]
    })


def declared_column(role):
    """The column a role keyword places its function in (honest-design section 3.1)."""
    if role not in COLUMNS:
        raise KeyError(f"no column for role {role!r}; the four-column model names {sorted(COLUMNS)}")
    return COLUMNS[role]


def undeclared_members(members, with_declaration):
    """Workspace members that carry no `.hd` and no exemption, sorted.

    `members` is what the workspace declares it contains and `with_declaration` is what was
    found to carry one; the difference is the finding. An exempt member is subtracted by name,
    never by noticing its file is missing.
    """
    return sorted(set(members) - set(with_declaration) - set(EXEMPT_FROM_DECLARATION))
