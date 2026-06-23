"""honest-persist - schema-first, pure-function persistence.

Schema as data, migrations as a pure diff, queries as data. I/O only at the boundary.
"""

from honest_persist.apply import apply, reconstruction_sql, requires_reconstruction, to_sql
from honest_persist.check import check_holds, parse_check
from honest_persist.execute import execute, execute_many, execute_one, execute_scalar
from honest_persist.instrumented import emit_pool_event, instrumented_execute
from honest_persist.pool import (
    POOL_LIFECYCLES,
    empty_pool_registry,
    get_pool,
    is_idle,
    reap_idle,
    recreate_ephemeral,
    resolve_pool_key,
)
from honest_persist.queue import (
    backoff_delay,
    drain_queue,
    empty_write_queue,
    enqueue_write,
    is_stalled,
    merge_pending,
    queue_from_jsonl,
    queue_to_jsonl,
)
from honest_persist.supervisor import load_queue, save_queue, supervise_drain
from honest_persist.query import (
    checked_delete,
    checked_insert,
    checked_select,
    checked_update,
    delete,
    insert,
    raw,
    select,
    update,
)
from honest_persist.transaction import transaction
from honest_persist.schema import diff, validate_schema
from honest_persist.instrument import (
    POOL_FAULT_CODES,
    build_migration_event,
    build_pool_event,
    build_query_event,
    extract_table,
    pool_fault,
    sql_hash,
)
from honest_persist.types import (
    Ambiguity,
    Column,
    Constraint,
    DiffResult,
    Index,
    Operation,
    Query,
    Table,
    diff_result,
    operation,
)

__all__ = [
    "diff",
    "validate_schema",
    "apply",
    "to_sql",
    "requires_reconstruction",
    "reconstruction_sql",
    "parse_check",
    "check_holds",
    "select",
    "insert",
    "update",
    "delete",
    "raw",
    "checked_select",
    "checked_insert",
    "checked_update",
    "checked_delete",
    "execute",
    "execute_one",
    "execute_scalar",
    "execute_many",
    "transaction",
    "operation",
    "diff_result",
    "Column",
    "Index",
    "Constraint",
    "Table",
    "Operation",
    "Query",
    "Ambiguity",
    "DiffResult",
    "POOL_FAULT_CODES",
    "pool_fault",
    "extract_table",
    "sql_hash",
    "build_query_event",
    "build_migration_event",
    "build_pool_event",
    "instrumented_execute",
    "emit_pool_event",
    "POOL_LIFECYCLES",
    "resolve_pool_key",
    "empty_pool_registry",
    "get_pool",
    "is_idle",
    "reap_idle",
    "recreate_ephemeral",
    "empty_write_queue",
    "enqueue_write",
    "merge_pending",
    "drain_queue",
    "queue_to_jsonl",
    "queue_from_jsonl",
    "backoff_delay",
    "is_stalled",
    "save_queue",
    "load_queue",
    "supervise_drain",
]
