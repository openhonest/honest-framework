"""Schema layer (section 5): the pure diff.

`diff(current, target)` compares two schemas with set theory and produces the operations that
transform `current` into `target`, ordered so dependencies are respected. Pure: same inputs,
same output, no I/O. Migrations are a diff, not a revision chain.

Table, column, foreign-key, index, and constraint changes are all set-theory diffs.
renamed_from hints distinguish a rename from a drop+add. The operations are then dependency-
ordered (section 5.4); a cycle in the dependency graph is a schema design error and returns a
fault. Ambiguity detection (section 5.3) and apply() (section 5.2) are separate.
"""

import json

from honest_type import err, fault, ok

from honest_persist.ambiguity import detect_ambiguities
from honest_persist.deps import build_dependencies, topological_sort
from honest_persist.types import diff_result, operation

# The extended-object maps of a SchemaDefinition and the `kind` each is stored under in the
# `_hp_object` registry (section 9.1).
_REGISTRY_KINDS = (("views", "view"), ("triggers", "trigger"), ("procedures", "procedure"))


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
            fk = {"column": column, "references": target_ref}
            for action in ("on_delete", "on_update"):
                if target_cols[column].get(action):
                    fk[action] = target_cols[column][action]
            ops.append(operation("add_foreign_key", table, fk))
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


def _normalize(schema):
    """Coerce a bare Schema (dict[str, Table]) or a SchemaDefinition into a full definition
    (section 4.15). A dict whose keys are a subset of the reserved names and that carries
    `tables` is a definition; anything else is a tables-only schema."""
    if "tables" in schema and set(schema) <= {"tables", "views", "triggers", "procedures"}:
        return {
            "tables": schema.get("tables", {}),
            "views": schema.get("views", {}),
            "triggers": schema.get("triggers", {}),
            "procedures": schema.get("procedures", {}),
        }
    return {"tables": schema, "views": {}, "triggers": {}, "procedures": {}}


def _constraint_registry_rows(tables):
    """The `_hp_object` rows recording each table's check constraints (section 9.1): a check constraint
    is an opaque SQL expression the database re-renders (PostgreSQL) or does not expose at all (SQLite),
    so honest-persist stores it in the registry and reads it back exactly rather than from the catalog.
    Each row is keyed 'table.constraint' and carries the table, the constraint name, and its definition.
    Pure."""
    rows = []
    for table_name in sorted(tables):
        constraints = tables[table_name].get("constraints", {})
        for constraint_name in sorted(constraints):
            if constraints[constraint_name].get("type") == "check":
                rows.append((table_name + "." + constraint_name, {"table": table_name, "constraint": constraint_name, "definition": constraints[constraint_name]}))
    return rows


def object_registry_queries(schema, dialect):
    """The queries that bring the `_hp_object` registry (section 9.1) in step with a schema's extended
    objects and check constraints, run after apply in the same workflow slot as `enum_seed_queries`
    (section 6.1). Pure query builder: ensure the registry table exists, clear it, and record every
    view, trigger, procedure, and check constraint as a row carrying its canonical definition as JSON —
    so the inspector reconstructs each one exactly without ever parsing the database's rendered DDL.
    Clearing then re-recording lets the registry shed objects the schema has dropped. Returns a list of
    `{sql, params}`."""
    definition = _normalize(schema)
    queries = [
        {"sql": "CREATE TABLE IF NOT EXISTS _hp_object (name TEXT PRIMARY KEY, kind TEXT NOT NULL, definition TEXT NOT NULL)", "params": {}},
        {"sql": "DELETE FROM _hp_object", "params": {}},
    ]
    insert = "INSERT INTO _hp_object (name, kind, definition) VALUES (:name, :kind, :definition)"
    for key, kind in _REGISTRY_KINDS:
        for name in sorted(definition[key]):
            queries.append({"sql": insert, "params": {"name": name, "kind": kind, "definition": json.dumps(definition[key][name], sort_keys=True)}})
    for name, row in _constraint_registry_rows(definition["tables"]):
        queries.append({"sql": insert, "params": {"name": name, "kind": "constraint", "definition": json.dumps(row, sort_keys=True)}})
    return queries


def _plain_view_create_ops(name, view):
    """The op to create a plain (non-materialized) view (section 5.7)."""
    return [operation("create_view", "", {"view": name, "definition": dict(view), "depends_on": list(view.get("depends_on", []))})]


def _plain_view_drop_ops(name, view):
    """The op to drop a plain (non-materialized) view (section 5.7)."""
    return [operation("drop_view", "", {"view": name, "depends_on": list(view.get("depends_on", []))})]


def _matview_create_ops(name, view):
    """The op to create a materialized view (section 6.6): one dialect-agnostic create_matview carrying
    the whole definition, ordered after the sources it reads. apply renders it to the dialect's
    statements — native materialized view or backing table, plus any refresh triggers."""
    return [operation("create_matview", name, {"view": name, "definition": dict(view), "depends_on": list(view.get("depends_on", []))})]


def _matview_drop_ops(name, view):
    """The op to drop a materialized view (section 6.6): one drop_matview carrying the definition so
    apply knows which refresh triggers to drop alongside the storage. depends_on travels so it is
    ordered before the source tables its refresh triggers fire on (section 5.4)."""
    return [operation("drop_matview", name, {"view": name, "definition": dict(view), "depends_on": list(view.get("depends_on", []))})]


# Create/drop of a view dispatches on whether it is materialized (section 6.6): a plain view is a
# CREATE/DROP VIEW; a materialized view is a single create_matview / drop_matview that apply expands
# per dialect.
_VIEW_CREATE_OPS = {False: _plain_view_create_ops, True: _matview_create_ops}
_VIEW_DROP_OPS = {False: _plain_view_drop_ops, True: _matview_drop_ops}


def _create_view_ops(name, view):
    """The ops to create one view, plain or materialized (sections 5.7, 6.6)."""
    return _VIEW_CREATE_OPS[bool(view.get("materialized"))](name, view)


def _drop_view_ops(name, view):
    """The ops to drop one view, plain or materialized (sections 5.7, 6.6)."""
    return _VIEW_DROP_OPS[bool(view.get("materialized"))](name, view)


def _diff_views(current_views, target_views):
    """View add/drop/replace (section 5.7). A changed definition is a drop + create; a materialized
    view is a create_matview / drop_matview that apply expands per dialect (section 6.6). depends_on
    travels in the ops for dependency ordering (section 5.4)."""
    ops = []
    for name in sorted(set(current_views) - set(target_views)):
        ops.extend(_drop_view_ops(name, current_views[name]))
    for name in sorted(set(target_views) - set(current_views)):
        ops.extend(_create_view_ops(name, target_views[name]))
    for name in sorted(set(current_views) & set(target_views)):
        if current_views[name] == target_views[name]:
            continue
        ops.extend(_drop_view_ops(name, current_views[name]))
        ops.extend(_create_view_ops(name, target_views[name]))
    return ops


def _diff_triggers(current_triggers, target_triggers):
    """Trigger add/drop/replace (section 5.7). The op's table is the table the trigger fires
    on, so it orders after that table (section 5.4)."""
    ops = []
    for name in sorted(set(current_triggers) - set(target_triggers)):
        ops.append(operation("drop_trigger", current_triggers[name].get("table", ""), {"trigger": name}))
    for name in sorted(set(target_triggers) - set(current_triggers)):
        trigger = target_triggers[name]
        ops.append(operation("create_trigger", trigger.get("table", ""), {"trigger": name, "definition": dict(trigger)}))
    for name in sorted(set(current_triggers) & set(target_triggers)):
        if current_triggers[name] == target_triggers[name]:
            continue
        trigger = target_triggers[name]
        ops.append(operation("drop_trigger", current_triggers[name].get("table", ""), {"trigger": name}))
        ops.append(operation("create_trigger", trigger.get("table", ""), {"trigger": name, "definition": dict(trigger)}))
    return ops


def _diff_procedures(current_procs, target_procs):
    """Procedure/function add/drop/replace (section 5.7). Functions use replace semantics
    (CREATE OR REPLACE); procedures without replace are drop + create."""
    ops = []
    for name in sorted(set(current_procs) - set(target_procs)):
        ops.append(operation("drop_function", "", {"function": name}))
    for name in sorted(set(target_procs) - set(current_procs)):
        ops.append(operation("create_function", "", {"function": name, "definition": dict(target_procs[name])}))
    for name in sorted(set(current_procs) & set(target_procs)):
        if current_procs[name] == target_procs[name]:
            continue
        proc = target_procs[name]
        if proc.get("kind", "function") == "function":
            ops.append(operation("replace_function", "", {"function": name, "definition": dict(proc)}))
            continue
        ops.append(operation("drop_function", "", {"function": name}))
        ops.append(operation("create_function", "", {"function": name, "definition": dict(proc)}))
    return ops


def _reference_error(references, schema):
    """None if the 'table.column' reference resolves in the schema, else an error string."""
    parts = references.split(".")
    if len(parts) != 2:
        return f"malformed reference '{references}' (expected 'table.column')"
    ref_table, ref_column = parts
    if ref_table not in schema:
        return f"references unknown table '{ref_table}'"
    if ref_column not in schema[ref_table].get("columns", {}):
        return f"references unknown column '{ref_table}.{ref_column}'"
    return None


def _table_errors(table_name, table, schema):
    """Internal-consistency errors for one table (section 5.6): dangling foreign keys, and
    primary-key / index / constraint references to columns that do not exist."""
    columns = table.get("columns", {})
    errors = []
    for column_name, column in columns.items():
        references = column.get("references")
        if references:
            problem = _reference_error(references, schema)
            if problem:
                errors.append(f"{table_name}.{column_name} {problem}")
    for column_name in table.get("primary_key", []):
        if column_name not in columns:
            errors.append(f"{table_name}: primary_key names missing column '{column_name}'")
    for index_name, index in table.get("indexes", {}).items():
        for column_name in index.get("columns", []):
            if column_name not in columns:
                errors.append(f"{table_name}.{index_name}: index names missing column '{column_name}'")
    for constraint_name, constraint in table.get("constraints", {}).items():
        for column_name in constraint.get("columns", []) or []:
            if column_name not in columns:
                errors.append(f"{table_name}.{constraint_name}: constraint names missing column '{column_name}'")
    return errors


def validate_schema(schema):
    """Check a schema for internal consistency before it is diffed or applied (section 5.6).
    Accepts a bare Schema or a SchemaDefinition (section 4.15). Returns ok(schema), or
    err(fault 'schema_invalid') listing every broken reference. Pure."""
    definition = _normalize(schema)
    tables = definition["tables"]
    errors = []
    for table_name, table in tables.items():
        errors.extend(_table_errors(table_name, table, tables))
    known = set(tables) | set(definition["views"])
    for view_name, view in definition["views"].items():
        for dependency in view.get("depends_on", []):
            if dependency not in known:
                errors.append(f"view '{view_name}' depends_on unknown object '{dependency}'")
    if errors:
        return err(fault("schema_invalid", "Schema has broken references", "server", {"errors": errors}))
    return ok(schema)


def _canonical_columns(tables):
    """Canonicalize columns so schemas that mean the same thing compare equal (section 5.1): a
    primary-key column is not-null, whether declared with a column-level `primary_key` or named in the
    table's `primary_key` list. This is what lets a declared `{primary_key: True}` round-trip against
    an inspected column, which every dialect reports as not-null. Pure."""
    result = {}
    for name, table in tables.items():
        pk_names = set(table.get("primary_key", []))
        columns = {}
        for column_name, column in table.get("columns", {}).items():
            columns[column_name] = {**column, "nullable": False} if (column.get("primary_key") or column_name in pk_names) else column
        result[name] = {**table, "columns": columns}
    return result


def diff(current, target, decisions=None):
    """Operations to transform the `current` schema into the `target` schema (section 5.1),
    dependency-ordered (section 5.4). Pure. Returns a DiffResult, or err(fault) when the target
    schema is invalid (section 5.6) or the dependency graph has a cycle (section 5.4)."""
    current_def = _normalize(current)
    target_def = _normalize(target)
    invalid = validate_schema(target_def)
    if "err" in invalid:
        return invalid
    current_tables = _canonical_columns(current_def["tables"])
    target_tables = _canonical_columns(target_def["tables"])
    dropped = set(current_tables) - set(target_tables)
    added = set(target_tables) - set(current_tables)
    modified = set(current_tables) & set(target_tables)
    renames, actual_adds = _resolve_renames(added, dropped, target_tables)
    rename_sources = {source for source, _ in renames}

    operations = []
    for table in sorted(dropped):
        if table not in rename_sources:
            operations.append(operation("drop_table", table, {"columns": dict(current_tables[table].get("columns", {}))}))
    for source, target_name in renames:
        operations.append(operation("rename_table", source, {"new_name": target_name}))
    for table in actual_adds:
        operations.append(operation("create_table", table, dict(target_tables[table])))
        for index_name in sorted(target_tables[table].get("indexes", {})):
            operations.append(operation("add_index", table, {"index": index_name, "definition": dict(target_tables[table]["indexes"][index_name])}))
    for table in sorted(modified):
        operations.extend(_diff_table(table, current_tables[table], target_tables[table]))
    operations.extend(_diff_views(current_def["views"], target_def["views"]))
    operations.extend(_diff_triggers(current_def["triggers"], target_def["triggers"]))
    operations.extend(_diff_procedures(current_def["procedures"], target_def["procedures"]))

    dependencies = build_dependencies(operations)
    execution_order = topological_sort(operations, dependencies)
    if execution_order is None:
        return err(fault(
            "schema_cycle", "Schema dependency graph contains a cycle", "server",
            {"operations": operations}))
    ambiguities = detect_ambiguities(current_tables, target_tables, decisions or {})
    return diff_result(operations, dependencies, execution_order, ambiguities)
