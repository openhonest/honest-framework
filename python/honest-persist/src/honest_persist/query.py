"""Query compilation + execution. SELECT only; mutations go through
compile_guarded_mutation.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from honest_persist.types import Query, Row


def compile_query(
    table: str,
    columns: list[str] | None = None,
    where: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> Query:
    """Pure. Build a parameterised SELECT."""
    cols = ", ".join(columns) if columns else "*"
    sql_parts = [f"SELECT {cols} FROM {table}"]
    params: list[Any] = []
    if where:
        conds = []
        for k, v in where.items():
            conds.append(f"{k} = ?")
            params.append(v)
        sql_parts.append("WHERE " + " AND ".join(conds))
    if order_by:
        sql_parts.append(f"ORDER BY {order_by}")
    if limit is not None:
        sql_parts.append(f"LIMIT {int(limit)}")
    return Query(sql=" ".join(sql_parts), params=params)


def execute(conn: sqlite3.Connection, query: Query) -> list[Row]:
    """Boundary. Run a compiled query; return rows as dicts."""
    cursor = conn.execute(query["sql"], query["params"])
    return [dict(row) for row in cursor.fetchall()]
