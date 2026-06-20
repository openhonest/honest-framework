"""Schema layer (section 5): the pure diff.

`diff(current, target)` compares two schemas with set theory and produces the operations that
transform `current` into `target`, ordered so dependencies are respected. Pure: same inputs,
same output, no I/O. Migrations are a diff, not a revision chain.

Table, column, foreign-key, index, and constraint changes are all set-theory diffs.
renamed_from hints distinguish a rename from a drop+add. The operations are then dependency-
ordered (section 5.4); a cycle in the dependency graph is a schema design error and returns a
fault. Ambiguity detection (section 5.3) and apply() (section 5.2) are separate.
"""

from honest_type import err, fault

from honest_persist.ambiguity import detect_ambiguities
from honest_persist.deps import build_dependencies, topological_sort
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


def _diff_columns(table, current_cols, target_cols):
    """Column add / drop / rename / alter for a table present in both schemas (section 5.1)."""
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


def _diff_foreign_keys(table, current_cols, target_cols):
    """Foreign-key changes on columns present in both schemas: a changed `references` is a drop
    of the old FK and an add of the new (section 5.1). New columns carry their FK in the
    add_column definition; this handles changes to existing columns."""
    ops = []
    for column in sorted(set(current_cols) & set(target_cols)):
        current_ref = current_cols[column].get("references")
        target_ref = target_cols[column].get("references")
        if current_ref == target_ref:
            continue
        if current_ref:
            ops.append(operation("drop_foreign_key", table, {"column": column, "references": current_ref}))
        if target_ref:
            ops.append(operation("add_foreign_key", table, {"column": column, "references": target_ref}))
    return ops


def _diff_named(table, current_named, target_named, add_op, drop_op, key):
    """Set-theory diff for named sub-objects (indexes, constraints): added -> add, dropped ->
    drop, changed -> drop + add."""
    dropped = set(current_named) - set(target_named)
    added = set(target_named) - set(current_named)
    common = set(current_named) & set(target_named)

    ops = []
    for name in sorted(dropped):
        ops.append(operation(drop_op, table, {key: name}))
    for name in sorted(added):
        ops.append(operation(add_op, table, {key: name, "definition": dict(target_named[name])}))
    for name in sorted(common):
        if current_named[name] != target_named[name]:
            ops.append(operation(drop_op, table, {key: name}))
            ops.append(operation(add_op, table, {key: name, "definition": dict(target_named[name])}))
    return ops


def _diff_table(table, current_table, target_table):
    """Every change to a table present in both schemas: columns, foreign keys, indexes,
    constraints (section 5.1)."""
    current_cols = current_table.get("columns", {})
    target_cols = target_table.get("columns", {})
    ops = _diff_columns(table, current_cols, target_cols)
    ops.extend(_diff_foreign_keys(table, current_cols, target_cols))
    ops.extend(_diff_named(
        table, current_table.get("indexes", {}), target_table.get("indexes", {}),
        "add_index", "drop_index", "index"))
    ops.extend(_diff_named(
        table, current_table.get("constraints", {}), target_table.get("constraints", {}),
        "add_constraint", "drop_constraint", "constraint"))
    return ops


def diff(current, target, decisions=None):
    """Operations to transform the `current` schema into the `target` schema (section 5.1),
    dependency-ordered (section 5.4). Pure. Returns a DiffResult, or err(fault) when the
    dependency graph has a cycle (a schema design error)."""
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
        operations.extend(_diff_table(table, current[table], target[table]))

    dependencies = build_dependencies(operations)
    execution_order = topological_sort(operations, dependencies)
    if execution_order is None:
        return err(fault(
            "schema_cycle", "Schema dependency graph contains a cycle", "server",
            {"operations": operations}))
    ambiguities = detect_ambiguities(current, target, decisions or {})
    return diff_result(operations, dependencies, execution_order, ambiguities)
