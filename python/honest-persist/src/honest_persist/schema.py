"""Schema layer (section 5): the pure diff.

`diff(current, target)` compares two schemas with set theory and produces the operations that
transform `current` into `target`. Pure: same inputs, same output, no I/O. Migrations are a
diff, not a revision chain.

Increment 1 generates table and column operations in a provably-safe emit order — drops, then
renames, then creates, then column modifications. The full dependency graph and topological
sort (section 5.4) and ambiguity detection (section 5.3) land with the foreign-key / index /
constraint operations that require them; for the operations generated here the emit order is
already valid, so execution_order is that order and dependencies / ambiguities are empty.
"""

from honest_persist.types import diff_result, operation


def _resolve_renames(added, dropped, target_mapping):
    """Split `added` names into (renames, actual_adds) using renamed_from hints: an added name
    whose renamed_from is a dropped name is a rename, not a fresh add (section 5.1)."""
    renames = []
    actual_adds = []
    for name in sorted(added):
        source = target_mapping[name].get("renamed_from")
        if source and source in dropped:
            renames.append((source, name))
        else:
            actual_adds.append(name)
    return renames, actual_adds


def _compute_alterations(current_col, target_col):
    """Type / nullable / default changes between two column definitions (section 5.1). An
    empty dict means no change."""
    changes = {}
    if current_col.get("type") != target_col.get("type"):
        changes["type"] = {"from": current_col.get("type"), "to": target_col.get("type")}
    if current_col.get("nullable", True) != target_col.get("nullable", True):
        changes["nullable"] = {
            "from": current_col.get("nullable", True),
            "to": target_col.get("nullable", True),
        }
    if current_col.get("default") != target_col.get("default"):
        changes["default"] = {"from": current_col.get("default"), "to": target_col.get("default")}
    return changes


def _diff_columns(table, current_table, target_table):
    """Column-level operations for a table present in both schemas (section 5.1)."""
    current_cols = current_table.get("columns", {})
    target_cols = target_table.get("columns", {})
    dropped = set(current_cols) - set(target_cols)
    added = set(target_cols) - set(current_cols)
    common = set(current_cols) & set(target_cols)
    renames, actual_adds = _resolve_renames(added, dropped, target_cols)
    rename_sources = {source for source, _ in renames}

    ops = []
    for column in sorted(dropped):
        if column not in rename_sources:
            ops.append(operation("drop_column", table, {"column": column}))
    for source, target_name in renames:
        ops.append(operation("rename_column", table, {"from": source, "to": target_name}))
    for column in actual_adds:
        ops.append(operation("add_column", table, {"column": column, "definition": dict(target_cols[column])}))
    for column in sorted(common):
        changes = _compute_alterations(current_cols[column], target_cols[column])
        if changes:
            ops.append(operation("alter_column", table, {"column": column, "changes": changes}))
    return ops


def diff(current, target, decisions=None):
    """Operations to transform the `current` schema into the `target` schema (section 5.1).
    Pure: no I/O, same inputs produce the same DiffResult."""
    dropped = set(current) - set(target)
    added = set(target) - set(current)
    modified = set(current) & set(target)
    renames, actual_adds = _resolve_renames(added, dropped, target)
    rename_sources = {source for source, _ in renames}

    operations = []
    for table in sorted(dropped):
        if table not in rename_sources:
            operations.append(operation("drop_table", table, {}))
    for source, target_name in renames:
        operations.append(operation("rename_table", source, {"new_name": target_name}))
    for table in actual_adds:
        operations.append(operation("create_table", table, dict(target[table])))
    for table in sorted(modified):
        operations.extend(_diff_columns(table, current[table], target[table]))

    execution_order = list(range(len(operations)))
    return diff_result(operations, {}, execution_order, [])
