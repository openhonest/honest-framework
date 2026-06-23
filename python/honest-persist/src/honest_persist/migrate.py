"""The migration workflow (section 9): inspect the live database, diff against the target, apply.

honest-persist has no revision chain. The schema is the source of truth, and a migration is the
diff between the live database and that schema, computed fresh every time. This module is the
workflow that ties the pieces together: read the current schema from the database (`inspect`, I/O,
dialect-specific), compute the diff against the target (`diff`, pure, section 5.1), refuse if the
diff is ambiguous so a human can decide (section 9 step 4), and otherwise apply (`apply`, I/O,
section 5.2). The orchestrator performs no catch — a failed inspect, an invalid target, and an
ambiguous diff all flow back as typed faults, exactly as everywhere else.

The inspector is dialect-specific and implementation-defined (section 12): each dialect reads its
own catalog. SQLite is read through `sqlite_master` and `PRAGMA table_info`. Resolving a column's
PRAGMA row to a column definition is pure; only the catalog reads are I/O.
"""

from honest_type import err, fault, ok

from honest_persist.abstractions import enum_seed_queries, expand_schema
from honest_persist.apply import apply
from honest_persist.schema import diff


def _column_from_pragma_row(row):
    """One `PRAGMA table_info` row to a column definition (section 9). The declared type is lowered
    so it round-trips against a schema declared in lower case; the primary-key flag and the default
    appear only when present, matching how a schema omits them. Pure."""
    column = {"type": row["type"].lower(), "nullable": row["notnull"] == 0}
    if row["pk"] > 0:
        column["primary_key"] = True
    if row["dflt_value"] is not None:
        column["default"] = row["dflt_value"]
    return column


def _columns_from_pragma(rows):
    """The `PRAGMA table_info` rows of one table to its column definitions (section 9). Pure."""
    return {row["name"]: _column_from_pragma_row(row) for row in rows}


async def _inspect_sqlite(conn):
    """Read the live schema of a SQLite database (section 9): list the user tables from
    `sqlite_master`, then read each table's columns through `PRAGMA table_info`. I/O. Returns
    ok(schema) — a bare Schema of table name to {columns}."""
    listing = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    schema = {}
    for row in listing["rows"]:
        name = row["name"]
        info = await conn.execute("PRAGMA table_info(" + name + ")")
        schema[name] = {"columns": _columns_from_pragma(info["rows"])}
    return ok(schema)


# The inspector for each supported dialect (section 9, 12). Each reads its own catalog.
_INSPECTORS = {"sqlite": _inspect_sqlite, "turso": _inspect_sqlite}


async def inspect(conn, dialect):
    """Read the live database's current schema (section 9 step 2). I/O, dialect-specific: it
    dispatches to the dialect's inspector. Returns ok(schema), or err(unsupported_dialect) when no
    inspector is registered for the dialect."""
    inspector = _INSPECTORS.get(dialect)
    if inspector is None:
        return err(fault("unsupported_dialect", f"no schema inspector for dialect '{dialect}'", "server", {}))
    return await inspector(conn)


async def migrate(schema, conn, dialect):
    """Run the full migration workflow against a live database (section 9): inspect the current
    schema, expand the target's abstractions (section 6), diff it against the live schema, refuse if
    the diff is ambiguous so a human can decide (section 9 step 4), apply, and seed the enum lookup
    tables idempotently (section 6.1). I/O orchestrator. Returns ok(ApplyResult), or err(fault) when
    inspection fails, the target is invalid, or the diff is ambiguous."""
    current = await inspect(conn, dialect)
    if "err" in current:
        return current
    expanded = expand_schema(schema)
    result = diff(current["ok"], expanded)
    if "err" in result:
        return result
    if result["ambiguities"]:
        return err(fault(
            "migration_ambiguous",
            "Diff is ambiguous; a human must resolve the renames before applying",
            "server",
            {"ambiguities": result["ambiguities"]},
        ))
    applied = await apply(result, expanded, conn, dialect)
    if applied["success"]:
        for query in enum_seed_queries(expanded, dialect):
            await conn.execute(query["sql"], query["params"])
    return ok(applied)
