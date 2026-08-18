"""The declared roles a module's `.hd` carries, read for the gate.

honest-check has always reconstructed a function's role from its Python decorator, and
`link(boundary=False)` carries one boolean. The declaration is richer: it separates
`boundary_in` from `boundary_out` and names the resource each one touches. So the gate has
been enforcing a coarser role than the author wrote down, and no rule about the direction of
the arrows between columns can be stated from Python alone (honest-design section 3.1).

The `.hd` is read through honest-design, which owns the format. Parsing it a second time here
would put one fact in two places, which is the drift this module exists to catch.
"""

from honest_design.reader import read_hd

# A function's column in the four-column model, keyed by the role keyword the author wrote.
# Read by subscript from a closed set: a keyword absent from it is a grammar change nobody
# taught this module about, and it must surface rather than resolve to a default column.
COLUMNS = {"boundary_in": 1, "orchestrator": 2, "fn": 3, "boundary_out": 4}


def declared_roles(source):
    """Map each function name in `.hd` source to the role keyword its author declared.

    Source that does not parse yields no roles rather than raising: the caller is the gate,
    and a malformed declaration is honest-design's fault to report, not a crash here.
    """
    document = read_hd(source)
    if "ok" not in document:
        return {}
    return {
        function["name"]: function["role"]
        for module in document["ok"]["modules"]
        for function in module["functions"]
    }


def declared_column(role):
    """The column a role keyword places its function in (honest-design section 3.1)."""
    if role not in COLUMNS:
        raise KeyError(f"no column for role {role!r}; the four-column model names {sorted(COLUMNS)}")
    return COLUMNS[role]
