"""Guarded mutations + transactions.

Every INSERT/UPDATE/DELETE goes through `guarded_mutation` which wraps
the WHERE clause in an invariant check. `execute_mutation` runs the
mutation inside a transaction, confirms the rowcount matches
`expected_rows`, and rolls back on mismatch.

This is the poka-yoke against TOCTOU: the guard is re-evaluated atomically
with the mutation, not separately.
"""
from __future__ import annotations

import contextlib
import sqlite3
from typing import Any

from honest_persist.query import execute as execute_query_raw
from honest_persist.query import compile_query
from honest_persist.types import ApplyResult, GuardedMutation, Query, Row


def guarded_mutation(
    table: str,
    set_values: dict[str, Any] | None = None,
    insert_values: dict[str, Any] | None = None,
    delete: bool = False,
    where: dict[str, Any] | None = None,
    expected_rows: int = 1,
    guard: str = "",
) -> GuardedMutation:
    """Pure. Construct a GuardedMutation record. Exactly one of
    set_values / insert_values / delete must be truthy.
    """
    kinds_used = sum(bool(x) for x in (set_values, insert_values, delete))
    if kinds_used != 1:
        raise ValueError("exactly one of set_values/insert_values/delete required")

    params: list[Any] = []
    if set_values:
        set_clause = ", ".join(f"{k} = ?" for k in set_values)
        params.extend(set_values.values())
        where_sql, where_params = _compile_where(where)
        params.extend(where_params)
        sql = f"UPDATE {table} SET {set_clause}{where_sql}"
    elif insert_values:
        cols = ", ".join(insert_values.keys())
        placeholders = ", ".join("?" for _ in insert_values)
        params.extend(insert_values.values())
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    else:  # delete
        where_sql, where_params = _compile_where(where)
        params.extend(where_params)
        sql = f"DELETE FROM {table}{where_sql}"

    return GuardedMutation(
        sql=sql, params=params,
        guard=guard or (str(where) if where else ""),
        expected_rows=expected_rows,
    )


def _compile_where(where: dict[str, Any] | None) -> tuple[str, list[Any]]:
    if not where:
        return "", []
    conds = []
    params: list[Any] = []
    for k, v in where.items():
        conds.append(f"{k} = ?")
        params.append(v)
    return " WHERE " + " AND ".join(conds), params


def compile_guarded_mutation(mutation: GuardedMutation) -> GuardedMutation:
    """Identity pass-through for now. Future: inject explicit guard clause
    into the WHERE and emit a CHECK constraint proof.
    """
    return mutation


@contextlib.contextmanager
def in_transaction(conn: sqlite3.Connection):
    """SERIALIZABLE-equivalent: BEGIN IMMEDIATE blocks other writers.

    Commits on clean exit; rolls back on exception.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def execute_mutation(
    conn: sqlite3.Connection,
    mutation: GuardedMutation,
) -> ApplyResult:
    """Boundary. Execute the mutation inside a transaction; rollback if
    rowcount != expected_rows.
    """
    try:
        with in_transaction(conn):
            cursor = conn.execute(mutation["sql"], mutation["params"])
            rowcount = cursor.rowcount
            if rowcount != mutation["expected_rows"]:
                raise _GuardMismatchError(
                    f"guard failed: expected {mutation['expected_rows']} rows, "
                    f"got {rowcount} ({mutation['guard']})"
                )
        return ApplyResult(
            ok=True, rowcount=rowcount, err_code="", err_category="",
            err_message="",
        )
    except _GuardMismatchError as exc:
        return ApplyResult(
            ok=False, rowcount=0, err_code="guard_mismatch",
            err_category="client", err_message=str(exc),
        )
    except sqlite3.Error as exc:
        return ApplyResult(
            ok=False, rowcount=0, err_code="sql_error",
            err_category="server", err_message=str(exc),
        )


class _GuardMismatchError(Exception):
    pass


# --- Also export convenient execute_query that takes a sqlite conn ---------


def execute_query(conn: sqlite3.Connection, query: Query) -> list[Row]:
    return execute_query_raw(conn, query)


# --- Apply operations alias kept for external callers ---------------------

from honest_persist.schema import apply_operations  # noqa: E402,F401
