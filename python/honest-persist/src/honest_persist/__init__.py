"""honest-persist - schema-first, pure-function persistence.

Schema as data, migrations as a diff, queries as data. Increment 1 (this release): the data
structures (section 4) and the pure schema diff (section 5.1).
"""

from honest_persist.apply import apply, reconstruction_sql, requires_reconstruction, to_sql
from honest_persist.check import check_holds, parse_check
from honest_persist.guards import GuardError, compile_guard, instantiate, provenance, validate_guard
from honest_persist.mutation import compile_guarded_mutation
from honest_persist.query import delete, insert, raw, select, update
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
    "validate_guard",
    "instantiate",
    "provenance",
    "compile_guard",
    "compile_guarded_mutation",
    "GuardError",
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
