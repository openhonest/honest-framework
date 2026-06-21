"""honest-persist - schema-first, pure-function persistence.

Schema as data, migrations as a pure diff, queries as data. I/O only at the boundary.
"""

from honest_persist.apply import apply, reconstruction_sql, requires_reconstruction, to_sql
from honest_persist.check import check_holds, parse_check
from honest_persist.execute import execute, execute_many, execute_one, execute_scalar
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
]
