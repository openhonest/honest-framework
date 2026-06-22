"""Pool-layer instrumentation (section 8): the typed pool faults and the pure event-payload builders
persist emits through honest-observe.

A persistence boundary instruments what happens *inside* the chain at the I/O boundary, feeding the
same event log as the request middleware (section 8.5). Everything here is pure data construction:
the payload a boundary hands to an injected `emit` (the one-way persist -> observe instrumentation,
never an import). The boundary itself — timing the query, calling emit, swallowing emit failures — is
the I/O layer that sits on top of these builders. Pool failures are typed faults, not exceptions
(section 8.3): the category distinguishes a caller error from a capacity or configuration error, so
the boundary maps it to the right HTTP status or log level.
"""

import hashlib
import re
from typing import Any, TypedDict

# Section 8.3: every pool-layer failure is one of these typed codes.
POOL_FAULT_CODES = frozenset(
    {
        "unknown_database",
        "unresolvable_dsn",
        "unknown_tenant",
        "pool_exhausted",
        "pool_closed",
        "credential_rejected",
        "lifecycle_failed",
    }
)

# Section 8.3: unknown_database / unknown_tenant are caller errors; the rest are capacity or
# configuration errors. The category drives the boundary's HTTP status / log level.
_POOL_FAULT_CATEGORY = {
    "unknown_database": "client",
    "unknown_tenant": "client",
    "unresolvable_dsn": "server",
    "pool_exhausted": "server",
    "pool_closed": "server",
    "credential_rejected": "server",
    "lifecycle_failed": "server",
}

_TABLE_PATTERN = re.compile(r"\b(?:FROM|INTO|UPDATE|TABLE)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


class PoolFault(TypedDict):
    code: str            # one of POOL_FAULT_CODES
    message: str
    category: str        # client | server


class QueryEvent(TypedDict):
    db_id: str
    table_name: str
    operation: str
    row_count: int
    duration_ns: int
    sql_hash: str
    sql: Any             # the full sql in development, else None
    request_id: Any      # the join key to the canonical request event, or None
    fault_code: Any      # present iff the query failed, else None


class MigrationEvent(TypedDict):
    db_id: str
    operation: str
    table: str
    detail: dict[str, Any]
    duration_ns: int
    sql: str
    success: bool
    fault_code: Any


class PoolEvent(TypedDict):
    db_id: str
    event: str           # created | exhausted | retry | closed | error
    pool_size: int
    active: int
    waiting: int
    duration_ns: Any     # uptime for "closed", else None
    fault_code: Any
    message: Any


def pool_fault(code, message) -> PoolFault:
    """A typed pool-layer fault (section 8.3). The category distinguishes a caller error from a
    capacity or configuration error. Pure; never raised."""
    return {"code": code, "message": message, "category": _POOL_FAULT_CATEGORY[code]}


def extract_table(sql) -> str:
    """The table a SQL statement targets (section 8.5): the identifier after FROM / INTO / UPDATE /
    TABLE, or "" when none is found. Pure."""
    match = _TABLE_PATTERN.search(sql)
    return match.group(1) if match else ""


def sql_hash(sql) -> str:
    """A stable SHA-256 hex digest of a SQL string (section 8.5). Always emitted; the full SQL is
    only emitted in development, so the hash groups and identifies queries without exposing
    parameter values. Pure and deterministic."""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def build_query_event(db_id, table, op, row_count, duration_ns, sql, request_id, fault_code, development_mode) -> QueryEvent:
    """The `hf.persist.query` payload (section 8.5), built after every query. `sql_hash` is always
    present; the full `sql` is included only in development mode. Pure."""
    return {
        "db_id": db_id,
        "table_name": table,
        "operation": op,
        "row_count": row_count,
        "duration_ns": duration_ns,
        "sql_hash": sql_hash(sql),
        "sql": sql if development_mode else None,
        "request_id": request_id,
        "fault_code": fault_code,
    }


def build_migration_event(db_id, op, table, detail, duration_ns, sql, success, fault_code) -> MigrationEvent:
    """The `hf.persist.migration` payload (section 8.7), built for each DDL operation `apply` runs —
    a complete schema-change history with no separate migration table. Pure."""
    return {
        "db_id": db_id,
        "operation": op,
        "table": table,
        "detail": detail,
        "duration_ns": duration_ns,
        "sql": sql,
        "success": success,
        "fault_code": fault_code,
    }


def build_pool_event(db_id, event, pool_size, active, waiting, duration_ns, fault_code, message) -> PoolEvent:
    """The `hf.persist.pool` payload (section 8.8), built on a pool lifecycle transition (created /
    exhausted / retry / closed / error), so pool health is in the same queryable log. Pure."""
    return {
        "db_id": db_id,
        "event": event,
        "pool_size": pool_size,
        "active": active,
        "waiting": waiting,
        "duration_ns": duration_ns,
        "fault_code": fault_code,
        "message": message,
    }
