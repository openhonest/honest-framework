"""honest-persist IR. All TypedDicts."""
from __future__ import annotations

from typing import Any, TypedDict


Row = dict[str, Any]


class Column(TypedDict):
    name: str
    type: str                 # SQL type, e.g. "TEXT", "INTEGER"
    nullable: bool
    default: Any              # Python value or None
    primary_key: bool


class Index(TypedDict):
    name: str
    columns: list[str]
    unique: bool


class Table(TypedDict):
    name: str
    columns: list[Column]
    indexes: list[Index]


class Schema(TypedDict):
    name: str
    tables: list[Table]


class Query(TypedDict):
    """Compiled SELECT. `sql` is the prepared statement; `params` are its
    positional arguments.
    """
    sql: str
    params: list[Any]


class GuardedMutation(TypedDict):
    """An INSERT/UPDATE/DELETE with an expressed guard predicate. The guard
    is the WHERE clause that must hold INSIDE the transaction for the
    mutation to take effect.
    """
    sql: str
    params: list[Any]
    guard: str                # human-readable guard description
    expected_rows: int        # rowcount we expect; apply fails otherwise


class Operation(TypedDict):
    """A schema migration operation."""
    kind: str                 # "create_table" | "add_column" | "drop_column" | ...
    target: str               # table name
    detail: dict[str, Any]    # operation-specific fields


class ApplyResult(TypedDict):
    ok: bool
    rowcount: int
    err_code: str
    err_category: str
    err_message: str
