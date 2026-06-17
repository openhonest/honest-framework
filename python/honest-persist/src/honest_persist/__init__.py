"""honest-persist — guarded mutations + transactions.

M1 uses SQLite as the backing store. The spec intends Turso embedded
(pyturso) in production; the public API is identical. Only the connect()
boundary changes between backends.
"""
from honest_persist.connection import close_connection, connect
from honest_persist.mutation import (
    apply_operations,
    compile_guarded_mutation,
    execute_mutation,
    execute_query,
    guarded_mutation,
    in_transaction,
)
from honest_persist.query import compile_query, execute
from honest_persist.schema import (
    Column,
    Index,
    Schema,
    Table,
    define_column,
    define_schema,
    define_table,
    diff_schema,
    inspect_schema,
    migrate_schema,
)
from honest_persist.types import (
    ApplyResult,
    GuardedMutation,
    Operation,
    Query,
    Row,
)

__all__ = [
    "ApplyResult",
    "Column",
    "GuardedMutation",
    "Index",
    "Operation",
    "Query",
    "Row",
    "Schema",
    "Table",
    "apply_operations",
    "close_connection",
    "compile_guarded_mutation",
    "compile_query",
    "connect",
    "define_column",
    "define_schema",
    "define_table",
    "diff_schema",
    "execute",
    "execute_mutation",
    "execute_query",
    "guarded_mutation",
    "in_transaction",
    "inspect_schema",
    "migrate_schema",
]
