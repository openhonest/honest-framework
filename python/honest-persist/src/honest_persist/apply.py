"""Schema apply (section 5.2): the I/O boundary.

`to_sql(operation, dialect)` is pure — it renders one operation to a DDL string, with dialect
differences resolved in lookup tables (no branching on dialect). `apply(diff, conn, dialect)`
is the boundary: it refuses to run while ambiguities are unresolved, executes the operations in
execution_order against the connection, halts on the first failure, and records what ran in an
ApplyResult. It also emits one `hf.persist.migration` per operation through an INJECTED emit
(section 8.7) — the one-way persist -> observe instrumentation, never an import — so schema history
joins the unified event log; a failing emit is swallowed, never breaking a migration, and no emit
means no events. Catching at the boundary, reading the clock, naming the fault from the exception,
and logging a swallowed emit to stderr are all boundary behaviours, so HC-P002/P004/P005 are
disabled file-wide here.

DDL is rendered in standard SQL; the type map resolves abstract types per dialect. alter_column
is rendered in the PostgreSQL form; dialects without in-place column alteration (sqlite) require
a table rebuild, emitted as one `reconstruct_table` migration event.
"""

# honest: disable HC-P002, HC-P004, HC-P005

import sys
import time

from honest_persist.instrument import build_migration_event
from honest_persist.schema import _normalize

_TYPE_MAP = {
    "postgresql": {"uuid": "uuid", "timestamptz": "timestamptz", "boolean": "boolean", "jsonb": "jsonb"},
    "sqlite": {"uuid": "text", "timestamptz": "text", "boolean": "integer", "jsonb": "text"},
    "turso": {"uuid": "text", "timestamptz": "text", "boolean": "integer", "jsonb": "text"},
}

_NULLABLE_ACTION = {True: "DROP NOT NULL", False: "SET NOT NULL"}


def _sql_type(abstract, dialect):
    return _TYPE_MAP.get(dialect, {}).get(abstract, abstract)


def _column_ddl(name, definition, dialect):
    parts = [name, _sql_type(definition.get("type", "text"), dialect)]
    if definition.get("primary_key"):
        parts.append("PRIMARY KEY")
    if not definition.get("nullable", True):
        parts.append("NOT NULL")
    if definition.get("unique"):
        parts.append("UNIQUE")
    if definition.get("default") is not None:
        parts.append(f"DEFAULT {definition['default']}")
    if definition.get("references"):
        ref_table, ref_column = definition["references"].rsplit(".", 1)
        parts.append(f"REFERENCES {ref_table}({ref_column})")
        if definition.get("on_delete"):
            parts.append(f"ON DELETE {definition['on_delete'].upper()}")
        if definition.get("on_update"):
            parts.append(f"ON UPDATE {definition['on_update'].upper()}")
    if definition.get("check"):
        parts.append(f"CHECK ({definition['check']})")
    return " ".join(parts)


def _render_create_table(op, dialect):
    table = op["details"]
    columns = table.get("columns", {})
    parts = [_column_ddl(name, columns[name], dialect) for name in columns]
    for name, constraint in table.get("constraints", {}).items():
        if constraint.get("type") == "check" and constraint.get("expression"):
            parts.append(f"CONSTRAINT {name} CHECK ({constraint['expression']})")
    return f"CREATE TABLE {op['table']} ({', '.join(parts)})"


def _render_drop_table(op, dialect):
    return f"DROP TABLE {op['table']}"


def _render_rename_table(op, dialect):
    return f"ALTER TABLE {op['table']} RENAME TO {op['details']['new_name']}"


def _render_add_column(op, dialect):
    details = op["details"]
    return f"ALTER TABLE {op['table']} ADD COLUMN {_column_ddl(details['column'], details['definition'], dialect)}"


def _render_drop_column(op, dialect):
    return f"ALTER TABLE {op['table']} DROP COLUMN {op['details']['column']}"


def _render_rename_column(op, dialect):
    details = op["details"]
    return f"ALTER TABLE {op['table']} RENAME COLUMN {details['from']} TO {details['to']}"


def _render_alter_column(op, dialect):
    column = op["details"]["column"]
    changes = op["details"].get("changes", {})
    clauses = []
    if "type" in changes:
        clauses.append(f"ALTER COLUMN {column} TYPE {_sql_type(changes['type']['to'], dialect)}")
    if "nullable" in changes:
        clauses.append(f"ALTER COLUMN {column} {_NULLABLE_ACTION[bool(changes['nullable']['to'])]}")
    if "default" in changes:
        new_default = changes["default"]["to"]
        action = "DROP DEFAULT" if new_default is None else f"SET DEFAULT {new_default}"
        clauses.append(f"ALTER COLUMN {column} {action}")
    return "; ".join(f"ALTER TABLE {op['table']} {clause}" for clause in clauses)


def _render_add_index(op, dialect):
    details = op["details"]
    definition = details.get("definition", {})
    unique = "UNIQUE " if definition.get("unique") else ""
    columns = ", ".join(definition.get("columns", []))
    return f"CREATE {unique}INDEX {details['index']} ON {op['table']} ({columns})"


def _render_drop_index(op, dialect):
    return f"DROP INDEX {op['details']['index']}"


def _render_add_foreign_key(op, dialect):
    details = op["details"]
    ref_table, ref_column = details["references"].split(".")
    name = f"fk_{op['table']}_{details['column']}"
    clause = f"ALTER TABLE {op['table']} ADD CONSTRAINT {name} FOREIGN KEY ({details['column']}) REFERENCES {ref_table} ({ref_column})"
    if details.get("on_delete"):
        clause += f" ON DELETE {details['on_delete'].upper()}"
    if details.get("on_update"):
        clause += f" ON UPDATE {details['on_update'].upper()}"
    return clause


def _render_drop_foreign_key(op, dialect):
    details = op["details"]
    return f"ALTER TABLE {op['table']} DROP CONSTRAINT fk_{op['table']}_{details['column']}"


def _render_add_constraint(op, dialect):
    details = op["details"]
    expression = details.get("definition", {}).get("expression", "")
    return f"ALTER TABLE {op['table']} ADD CONSTRAINT {details['constraint']} CHECK ({expression})"


def _render_drop_constraint(op, dialect):
    return f"ALTER TABLE {op['table']} DROP CONSTRAINT {op['details']['constraint']}"


def _render_create_view(op, dialect):
    details = op["details"]
    return f"CREATE VIEW {details['view']} AS {details['definition']['query']}"


def _render_drop_view(op, dialect):
    return f"DROP VIEW {op['details']['view']}"


def _render_create_trigger(op, dialect):
    details = op["details"]
    trigger = details["definition"]
    events = " OR ".join(event.upper() for event in trigger["events"])
    parts = [f"CREATE TRIGGER {details['trigger']}", trigger["timing"].upper().replace("_", " "), events, f"ON {trigger['table']}"]
    if trigger.get("when"):
        parts.append(f"WHEN ({trigger['when']})")
    parts.append(trigger["body"])
    return " ".join(parts)


def _render_drop_trigger(op, dialect):
    return f"DROP TRIGGER {op['details']['trigger']}"


def _render_function(op, replace):
    details = op["details"]
    proc = details["definition"]
    params = ", ".join(f"{parameter['name']} {parameter['type']}" for parameter in proc.get("params", []))
    verb = "CREATE OR REPLACE" if replace else "CREATE"
    parts = [f"{verb} {proc.get('kind', 'function').upper()} {details['function']}({params})"]
    if proc.get("returns"):
        parts.append(f"RETURNS {proc['returns']}")
    if proc.get("language"):
        parts.append(f"LANGUAGE {proc['language']}")
    parts.append(f"AS {proc['body']}")
    return " ".join(parts)


def _render_create_function(op, dialect):
    return _render_function(op, False)


def _render_replace_function(op, dialect):
    return _render_function(op, True)


def _render_drop_function(op, dialect):
    return f"DROP FUNCTION {op['details']['function']}"


_RENDERERS = {
    "create_table": _render_create_table,
    "drop_table": _render_drop_table,
    "rename_table": _render_rename_table,
    "add_column": _render_add_column,
    "drop_column": _render_drop_column,
    "rename_column": _render_rename_column,
    "alter_column": _render_alter_column,
    "add_index": _render_add_index,
    "drop_index": _render_drop_index,
    "add_foreign_key": _render_add_foreign_key,
    "drop_foreign_key": _render_drop_foreign_key,
    "add_constraint": _render_add_constraint,
    "drop_constraint": _render_drop_constraint,
    "create_view": _render_create_view,
    "drop_view": _render_drop_view,
    "create_trigger": _render_create_trigger,
    "drop_trigger": _render_drop_trigger,
    "create_function": _render_create_function,
    "replace_function": _render_replace_function,
    "drop_function": _render_drop_function,
}


def to_sql(operation, dialect):
    """Render one operation to a DDL string for the dialect (section 5.2). Pure. Returns None
    for an operation type with no renderer."""
    renderer = _RENDERERS.get(operation["op"])
    if renderer is None:
        return None
    return renderer(operation, dialect)


def _apply_result(success, executed, error, error_operation):
    return {
        "success": success,
        "executed_sql": executed,
        "operations_applied": len(executed),
        "error": error,
        "error_operation": error_operation,
    }


# Operations that cannot be applied in place on a dialect and need a table rebuild (section 5.5).
_RECONSTRUCTION_OPS = {
    "postgresql": frozenset(),
    "sqlite": frozenset({"alter_column", "add_foreign_key", "drop_foreign_key", "drop_constraint"}),
    "turso": frozenset({"alter_column", "add_foreign_key", "drop_foreign_key", "drop_constraint"}),
}


def requires_reconstruction(operation, dialect):
    """True if an operation cannot be applied in place on the dialect and needs a table rebuild
    (section 5.5). Pure lookup."""
    return operation["op"] in _RECONSTRUCTION_OPS.get(dialect, frozenset())


def reconstruction_sql(table, target_table, common_columns, dialect, temp_name=None):
    """The statement sequence that rebuilds `table` into `target_table` (section 5.5): create a
    temp table with the target columns, copy the common columns, drop the old, rename the temp
    into place, recreate the target indexes. Pure. The transaction wrapping and foreign-key
    toggling are apply()'s boundary responsibility; `temp_name` carries the unique id apply()
    mints, with a deterministic default so the plan is reproducible for testing."""
    temp = temp_name or f"_hp_tmp_{table}"
    columns = target_table.get("columns", {})
    columns_ddl = ", ".join(_column_ddl(name, columns[name], dialect) for name in columns)
    statements = [f"CREATE TABLE {temp} ({columns_ddl})"]
    if common_columns:
        copied = ", ".join(common_columns)
        statements.append(f"INSERT INTO {temp} ({copied}) SELECT {copied} FROM {table}")
    statements.append(f"DROP TABLE {table}")
    statements.append(f"ALTER TABLE {temp} RENAME TO {table}")
    for index_name, index in target_table.get("indexes", {}).items():
        unique = "UNIQUE " if index.get("unique") else ""
        index_columns = ", ".join(index.get("columns", []))
        statements.append(f"CREATE {unique}INDEX {index_name} ON {table} ({index_columns})")
    return statements


def _columns_added(operations, table):
    """The columns added to a table by this diff — they did not exist before reconstruction, so
    they are not copied from the old table."""
    return {op["details"]["column"] for op in operations if op["op"] == "add_column" and op["table"] == table}


async def _pause_push(conn):
    if hasattr(conn, "pause_push"):
        await conn.pause_push()


async def _resume_push(conn):
    if hasattr(conn, "resume_push"):
        await conn.resume_push()


async def _reconstruct(table, target_tables, operations, conn, dialect, executed):
    """Rebuild one table to its target shape (section 5.5) with the full foreign-key lifecycle, pausing
    sync push for the duration (Turso). Foreign-key checks are disabled BEFORE the transaction — the
    pragma is connection-scoped, not transactional, so it cannot be toggled mid-transaction — the rebuild
    runs inside one transaction, step 6 verifies every foreign key still points at a real row, the
    transaction commits, and the foreign-key checks are re-enabled after. Any statement failure or a
    dangling foreign key rolls the whole transaction back (so a table is never left half-migrated) and
    still re-enables the checks, so the connection is never left with them off. Returns None on success,
    or an ApplyResult on failure. The exact transaction and foreign-key SQL is the connection's
    (dialect-specific, section 12); this orchestrates the control flow. I/O."""
    target_table = target_tables.get(table, {})
    added = _columns_added(operations, table)
    common = [name for name in target_table.get("columns", {}) if name not in added]
    await _pause_push(conn)
    await conn.disable_foreign_keys()
    await conn.begin()
    try:
        for sql in reconstruction_sql(table, target_table, common, dialect):
            await conn.execute(sql)
            executed.append(sql)
        violations = await conn.verify_foreign_keys()
    except Exception as exc:
        await conn.rollback()
        await conn.enable_foreign_keys()
        await _resume_push(conn)
        return _apply_result(False, executed, str(exc), None)
    if violations:
        await conn.rollback()
        await conn.enable_foreign_keys()
        await _resume_push(conn)
        return _apply_result(False, executed, f"foreign keys left dangling after reconstruction: {violations}", None)
    await conn.commit()
    await conn.enable_foreign_keys()
    await _resume_push(conn)
    return None


async def _emit_migration(emit, db_id, op, table, detail, sql, duration_ns, success, fault_code):
    """Emit one hf.persist.migration through the injected emit (section 8.7), keyed by the schema
    aggregate. A failure in emit is logged to stderr and swallowed — instrumentation must never break
    a migration. No-op when no emit is wired in. I/O."""
    if emit is None:
        return
    payload = build_migration_event(db_id, op, table, detail, duration_ns, sql, success, fault_code)
    try:
        await emit("hf.persist.migration", "schema", db_id + ":" + table, payload)
    except Exception as exc:
        print(f"honest-persist: migration event emit failed: {exc}", file=sys.stderr)


async def apply(diff_result, target, conn, dialect, emit=None, db_id=""):
    """Execute a DiffResult against the connection in execution_order (section 5.2). Async I/O
    boundary: refuses while ambiguities are unresolved, reconstructs tables that cannot be
    altered in place (section 5.5) — pausing sync push for the rebuild — halts on the first
    failure, and returns an ApplyResult. Emits one hf.persist.migration per operation through the
    injected emit (section 8.7); a reconstructed table emits one reconstruct_table event. Not pure:
    it awaits I/O through conn."""
    if diff_result.get("ambiguities"):
        return _apply_result(False, [], "unresolved ambiguities; resolve before applying", None)
    target_tables = _normalize(target)["tables"]
    operations = diff_result["operations"]
    reconstruct_tables = {op["table"] for op in operations if requires_reconstruction(op, dialect)}
    reconstructed = set()
    executed = []
    for index in diff_result["execution_order"]:
        op = operations[index]
        if op["table"] in reconstruct_tables:
            if op["table"] in reconstructed:
                continue
            start = time.perf_counter_ns()
            mark = len(executed)
            failure = await _reconstruct(op["table"], target_tables, operations, conn, dialect, executed)
            rebuilt_sql = "; ".join(executed[mark:])
            if failure is not None:
                await _emit_migration(emit, db_id, "reconstruct_table", op["table"], {}, rebuilt_sql, time.perf_counter_ns() - start, False, "reconstruction_failed")
                return failure
            await _emit_migration(emit, db_id, "reconstruct_table", op["table"], {}, rebuilt_sql, time.perf_counter_ns() - start, True, None)
            reconstructed.add(op["table"])
            continue
        sql = to_sql(op, dialect)
        if sql is None:
            return _apply_result(False, executed, f"no renderer for '{op['op']}'", index)
        start = time.perf_counter_ns()
        try:
            await conn.execute(sql)
        except Exception as exc:
            await _emit_migration(emit, db_id, op["op"], op["table"], op["details"], sql, time.perf_counter_ns() - start, False, type(exc).__name__)
            return _apply_result(False, executed, str(exc), index)
        executed.append(sql)
        await _emit_migration(emit, db_id, op["op"], op["table"], op["details"], sql, time.perf_counter_ns() - start, True, None)
    return _apply_result(True, executed, None, None)
# honest: enable HC-P002
