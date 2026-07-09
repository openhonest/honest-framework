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

import json

from honest_type import err, fault, ok

from honest_persist.abstractions import enum_seed_queries, expand_schema
from honest_persist.apply import apply
from honest_persist.check import validate_checks
from honest_persist.schema import diff, object_registry_queries

# The `kind` recorded in the `_hp_object` registry (section 9.1) maps to the SchemaDefinition map the
# reconstructed object belongs in.
_REGISTRY_MAP = {"view": "views", "trigger": "triggers", "procedure": "procedures"}


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


async def _read_object_registry(conn, exists_sql):
    """Reconstruct the extended objects (views, triggers, procedures) of a live database from the
    `_hp_object` registry (section 9.1). I/O, dialect-independent apart from the `exists_sql` that
    checks whether the registry table is there: each row's canonical definition is stored as JSON, so
    reconstruction is an exact round-trip that never parses the database's rendered DDL. A database
    honest-persist has not yet touched has no registry table and therefore no extended objects.
    Returns {views, triggers, procedures}."""
    objects = {"views": {}, "triggers": {}, "procedures": {}}
    present = await conn.execute(exists_sql)
    if not present["rows"]:
        return objects
    rows = await conn.execute("SELECT name, kind, definition FROM _hp_object")
    for row in rows["rows"]:
        objects[_REGISTRY_MAP[row["kind"]]][row["name"]] = json.loads(row["definition"])
    return objects


def _owned_tables(objects):
    """The stored tables that are honest-persist's own bookkeeping rather than user tables (section
    9.1): the `_hp_object` registry and every materialized view's backing table, which round-trips as
    a view instead. Pure."""
    return {"_hp_object"} | {name for name, view in objects["views"].items() if view.get("materialized")}


async def _inspect_sqlite(conn):
    """Read the complete live schema of a SQLite database (section 9.1): the user tables and their
    columns from `sqlite_master` and `PRAGMA table_info`, and the views, triggers, and procedures
    from the `_hp_object` registry. Owned tables (the registry, materialized-view backing tables) are
    not reported. I/O. Returns ok of a full SchemaDefinition (section 4.15)."""
    objects = await _read_object_registry(conn, "SELECT name FROM sqlite_master WHERE type = 'table' AND name = '_hp_object'")
    owned = _owned_tables(objects)
    listing = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = {}
    for row in listing["rows"]:
        name = row["name"]
        if name in owned:
            continue
        info = await conn.execute("PRAGMA table_info(" + name + ")")
        tables[name] = {"columns": _columns_from_pragma(info["rows"])}
    return ok({"tables": tables, **objects})


# A PostgreSQL information_schema data_type resolved back to honest-persist's abstract type (section
# 9.1). Only the non-identity forms honest-persist emits need an entry; every other type is itself.
_PG_TYPE = {"timestamp with time zone": "timestamptz"}


def _pg_type(data_type):
    """Resolve a PostgreSQL data_type back to honest-persist's abstract type (section 9.1). Pure."""
    return _PG_TYPE.get(data_type, data_type)


# The PostgreSQL catalog queries (section 9.1). One statement reads the registry's presence; one reads
# every public base table's columns, nullability, defaults, and primary-key membership in a single
# pass, so the inspector makes two reads and no per-table loop.
_PG_REGISTRY_EXISTS = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '_hp_object'"
_PG_SCHEMA = (
    "SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.column_default, "
    "CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key "
    "FROM information_schema.columns c "
    "JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE' "
    "LEFT JOIN (SELECT kcu.table_name, kcu.column_name FROM information_schema.table_constraints tc "
    "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
    "WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY') pk "
    "ON pk.table_name = c.table_name AND pk.column_name = c.column_name "
    "WHERE c.table_schema = 'public' ORDER BY c.table_name, c.ordinal_position"
)


def _pg_column(row):
    """One `_PG_SCHEMA` row to a column definition (section 9.1). The primary-key flag and default
    appear only when present, matching how a schema omits them. Pure."""
    column = {"type": _pg_type(row["data_type"]), "nullable": row["is_nullable"] == "YES"}
    if row["is_primary_key"]:
        column["primary_key"] = True
    if row["column_default"] is not None:
        column["default"] = row["column_default"]
    return column


def _pg_tables(rows, owned):
    """Assemble the tables map from the flat `_PG_SCHEMA` result (section 9.1): group the ordered rows
    by table, skip honest-persist's own bookkeeping tables, and resolve each column. Pure."""
    tables = {}
    for row in rows:
        name = row["table_name"]
        if name in owned:
            continue
        tables.setdefault(name, {"columns": {}})["columns"][row["column_name"]] = _pg_column(row)
    return tables


async def _inspect_postgresql(conn):
    """Read the complete live schema of a PostgreSQL database (section 9.1): the public base tables
    with their columns from `information_schema`, and the views, triggers, and procedures from the
    `_hp_object` registry. Thin I/O seam — the catalog SQL and the assembly are pure; this reads the
    registry and the one schema query and hands the rows to `_pg_tables`. Returns ok of a full
    SchemaDefinition (section 4.15)."""
    objects = await _read_object_registry(conn, _PG_REGISTRY_EXISTS)
    rows = await conn.execute(_PG_SCHEMA)
    return ok({"tables": _pg_tables(rows["rows"], _owned_tables(objects)), **objects})


# The inspector for each supported dialect (section 9, 9.1). Each reads its own catalog; the
# reconstruction contract is identical across dialects.
_INSPECTORS = {"sqlite": _inspect_sqlite, "turso": _inspect_sqlite, "postgresql": _inspect_postgresql}


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
    schema, expand the target's abstractions (section 6), refuse a CHECK that can be neither natively
    enforced on the dialect nor compiled (section 6.2), diff it against the live schema, refuse if
    the diff is ambiguous so a human can decide (section 9 step 4), apply, and seed the enum lookup
    tables idempotently (section 6.1). I/O orchestrator. Returns ok(ApplyResult), or err(fault) when
    inspection fails, the target is invalid, or the diff is ambiguous."""
    current = await inspect(conn, dialect)
    if "err" in current:
        return current
    expanded = expand_schema(schema)
    checked = validate_checks(expanded, dialect)
    if "err" in checked:
        return checked
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
        for query in object_registry_queries(expanded, dialect):
            await conn.execute(query["sql"], query["params"])
    return ok(applied)
