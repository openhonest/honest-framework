"""Schema apply (section 5.2): the I/O boundary.

`to_sql(operation, dialect)` is pure — it renders one operation to a DDL string, with dialect
differences resolved in lookup tables (no branching on dialect). `apply(diff, conn, dialect)`
is the boundary: it refuses to run while ambiguities are unresolved, executes the operations in
execution_order against the connection, halts on the first failure, and records what ran in an
ApplyResult. Catching at the boundary is by design, so HC-P002 is disabled file-wide here.

DDL is rendered in standard SQL; the type map resolves abstract types per dialect. alter_column
is rendered in the PostgreSQL form; dialects without in-place column alteration (sqlite) require
a table rebuild, which is a later concern.
"""

# honest: disable HC-P002

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
    return " ".join(parts)


def _render_create_table(op, dialect):
    columns = op["details"].get("columns", {})
    rendered = ", ".join(_column_ddl(name, columns[name], dialect) for name in columns)
    return f"CREATE TABLE {op['table']} ({rendered})"


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
    return f"ALTER TABLE {op['table']} ADD CONSTRAINT {name} FOREIGN KEY ({details['column']}) REFERENCES {ref_table} ({ref_column})"


def _render_drop_foreign_key(op, dialect):
    details = op["details"]
    return f"ALTER TABLE {op['table']} DROP CONSTRAINT fk_{op['table']}_{details['column']}"


def _render_add_constraint(op, dialect):
    details = op["details"]
    expression = details.get("definition", {}).get("expression", "")
    return f"ALTER TABLE {op['table']} ADD CONSTRAINT {details['constraint']} CHECK ({expression})"


def _render_drop_constraint(op, dialect):
    return f"ALTER TABLE {op['table']} DROP CONSTRAINT {op['details']['constraint']}"


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


def apply(diff_result, conn, dialect):
    """Execute a DiffResult against the connection in execution_order (section 5.2). The
    boundary: refuses while ambiguities are unresolved, halts on the first failure, and returns
    an ApplyResult recording what ran. Not pure — it performs I/O through conn."""
    if diff_result.get("ambiguities"):
        return _apply_result(False, [], "unresolved ambiguities; resolve before applying", None)
    operations = diff_result["operations"]
    executed = []
    for index in diff_result["execution_order"]:
        sql = to_sql(operations[index], dialect)
        if sql is None:
            return _apply_result(False, executed, f"no renderer for '{operations[index]['op']}'", index)
        try:
            conn.execute(sql)
        except Exception as exc:
            return _apply_result(False, executed, str(exc), index)
        executed.append(sql)
    return _apply_result(True, executed, None, None)
# honest: enable HC-P002
