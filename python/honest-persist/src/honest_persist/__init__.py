"""honest-persist - schema-first, pure-function persistence.

Schema as data, migrations as a diff, queries as data. Increment 1 (this release): the data
structures (section 4) and the pure schema diff (section 5.1).
"""

from honest_persist.apply import apply, to_sql
from honest_persist.schema import diff, validate_schema
from honest_persist.types import (
    Ambiguity,
    Column,
    Constraint,
    DiffResult,
    Index,
    Operation,
    Table,
    diff_result,
    operation,
)

__all__ = [
    "diff",
    "validate_schema",
    "apply",
    "to_sql",
    "operation",
    "diff_result",
    "Column",
    "Index",
    "Constraint",
    "Table",
    "Operation",
    "Ambiguity",
    "DiffResult",
]
