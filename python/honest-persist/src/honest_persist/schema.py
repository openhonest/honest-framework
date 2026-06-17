"""Schema types + constructors + migration diff.

Schema is a declarative dict. Migration is a diff between declared and
live shapes, compiled into a list of Operations.
"""
from __future__ import annotations

import sqlite3

from honest_persist.types import Column, Index, Operation, Schema, Table


# --- Constructors ----------------------------------------------------------


def define_column(
    name: str,
    type: str,
    nullable: bool = False,
    default = None,
    primary_key: bool = False,
) -> Column:
    return Column(
        name=name, type=type, nullable=nullable,
        default=default, primary_key=primary_key,
    )


def define_table(
    name: str,
    columns: list[Column],
    indexes: list[Index] | None = None,
) -> Table:
    return Table(name=name, columns=list(columns), indexes=list(indexes or []))


def define_schema(name: str, tables: list[Table]) -> Schema:
    return Schema(name=name, tables=list(tables))


# --- Inspection (boundary: reads live DB) ---------------------------------


def inspect_schema(conn: sqlite3.Connection) -> Schema:
    tables: list[Table] = []
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        t_name = row["name"]
        cols = [
            Column(
                name=c["name"], type=c["type"],
                nullable=not c["notnull"], default=c["dflt_value"],
                primary_key=bool(c["pk"]),
            )
            for c in conn.execute(f"PRAGMA table_info({t_name})")
        ]
        tables.append(Table(name=t_name, columns=cols, indexes=[]))
    return Schema(name="live", tables=tables)


# --- Diff (pure) ----------------------------------------------------------


def diff_schema(declared: Schema, live: Schema) -> list[Operation]:
    """Return the list of operations needed to bring `live` to `declared`.

    M1 handles: create_table, add_column. Drop is not emitted automatically
    (destructive).
    """
    ops: list[Operation] = []
    live_tables = {t["name"]: t for t in live["tables"]}
    for t in declared["tables"]:
        if t["name"] not in live_tables:
            ops.append(Operation(
                kind="create_table", target=t["name"],
                detail={"table": t},
            ))
            continue
        live_cols = {c["name"]: c for c in live_tables[t["name"]]["columns"]}
        for c in t["columns"]:
            if c["name"] not in live_cols:
                ops.append(Operation(
                    kind="add_column", target=t["name"],
                    detail={"column": c},
                ))
    return ops


# --- Apply (boundary) -----------------------------------------------------


def apply_operations(
    conn: sqlite3.Connection,
    ops: list[Operation],
) -> int:
    """Execute migration operations in order. Returns count applied."""
    applied = 0
    for op in ops:
        compiled = _compile_operation(op)
        conn.execute(compiled)
        applied += 1
    return applied


def _compile_operation(op: Operation) -> str:
    compiler = _OP_COMPILERS[op["kind"]]
    return compiler(op)


def _compile_create_table(op: Operation) -> str:
    t: Table = op["detail"]["table"]
    parts = []
    for c in t["columns"]:
        decl = f'{c["name"]} {c["type"]}'
        if c["primary_key"]:
            decl += " PRIMARY KEY"
        if not c["nullable"]:
            decl += " NOT NULL"
        if c["default"] is not None:
            decl += f' DEFAULT {_sql_literal(c["default"])}'
        parts.append(decl)
    return f'CREATE TABLE {t["name"]} ({", ".join(parts)})'


def _compile_add_column(op: Operation) -> str:
    c: Column = op["detail"]["column"]
    decl = f'{c["name"]} {c["type"]}'
    if not c["nullable"] and c["default"] is None:
        # SQLite: adding a NOT NULL column without default is disallowed.
        # Fall back to nullable.
        pass
    if c["default"] is not None:
        decl += f' DEFAULT {_sql_literal(c["default"])}'
    return f'ALTER TABLE {op["target"]} ADD COLUMN {decl}'


_OP_COMPILERS = {
    "create_table": _compile_create_table,
    "add_column":   _compile_add_column,
}


def _sql_literal(v) -> str:
    if isinstance(v, str):
        safe = v.replace("'", "''")
        return f"'{safe}'"
    if v is None:
        return "NULL"
    return str(v)


# --- Top-level migration orchestrator -------------------------------------


def migrate_schema(conn: sqlite3.Connection, declared: Schema) -> int:
    live = inspect_schema(conn)
    ops = diff_schema(declared, live)
    return apply_operations(conn, ops)
