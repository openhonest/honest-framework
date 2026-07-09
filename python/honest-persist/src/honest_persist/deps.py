"""Operation dependency ordering (section 5.4).

Some operations must precede others — a foreign key needs its referenced table to exist first,
a column drop must happen before its table is dropped. The rules are a lookup table, not
imperative logic. `order_operations` builds the graph and topologically sorts it; a cycle is a
schema design error and returns None (the caller raises a fault).
"""

# An operation of this type depends on (must run after) operations of the listed types on a
# related table (section 5.4).
_DEPENDS_ON = {
    "add_foreign_key": ("create_table",),
    "add_column": ("create_table",),
    "add_index": ("create_table", "add_column"),
    "add_constraint": ("create_table", "add_column"),
    "create_view": ("create_table", "create_view"),
    "create_matview": ("create_table", "create_view", "create_matview"),
    "create_trigger": ("create_table", "create_matview"),
}

# An operation of this type must precede (run before) operations of the listed types on a
# related table.
_MUST_PRECEDE = {
    "drop_foreign_key": ("drop_table", "drop_column"),
    "drop_index": ("drop_table", "drop_column"),
    "drop_constraint": ("drop_table", "drop_column"),
    "drop_column": ("drop_table",),
    "drop_view": ("drop_table",),
    "drop_trigger": ("drop_table", "drop_matview"),
}


def _subject(op):
    """The object an operation acts on: a view/trigger/function name, else the table."""
    details = op["details"]
    return details.get("view") or details.get("trigger") or details.get("function") or op["table"]


def _related(op_a, op_b):
    """Two operations are related when op_a touches the same table op_b does, op_a's foreign key
    references op_b's subject, or op_a declares op_b's subject in its depends_on."""
    subject_b = _subject(op_b)
    if op_a["table"] and op_a["table"] == op_b["table"]:
        return True
    references = op_a["details"].get("references", "")
    if references and references.split(".")[0] == subject_b:
        return True
    return subject_b in op_a["details"].get("depends_on", [])


def _runs_before(op_a, op_b):
    """True if op_a must execute before op_b under the rules."""
    if op_a["op"] in _DEPENDS_ON.get(op_b["op"], ()) and _related(op_b, op_a):
        return True
    return op_b["op"] in _MUST_PRECEDE.get(op_a["op"], ()) and _related(op_a, op_b)


def build_dependencies(operations):
    """op index -> [indices that must run before it] (section 5.4)."""
    deps = {i: [] for i in range(len(operations))}
    for later, op_later in enumerate(operations):
        for earlier, op_earlier in enumerate(operations):
            if earlier != later and _runs_before(op_earlier, op_later):
                deps[later].append(earlier)
    return deps


def topological_sort(operations, deps):
    """A valid execution order of operation indices, or None if the graph has a cycle. Ties
    break by index, so the order is deterministic."""
    indegree = {i: len(deps[i]) for i in range(len(operations))}
    dependents = {i: [] for i in range(len(operations))}
    for later, earlier_list in deps.items():
        for earlier in earlier_list:
            dependents[earlier].append(later)

    ready = sorted(i for i in indegree if indegree[i] == 0)
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in dependents[node]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort()
    if len(order) != len(operations):
        return None
    return order
