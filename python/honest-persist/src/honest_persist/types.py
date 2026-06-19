"""honest-persist data structures (section 4).

Plain dicts (TypedDict); JSON-serializable; no classes, no behaviour. A Schema is
dict[table_name, Table]; everything else is a record. Optional fields use total=False so a
hand-written or loader-produced dict need only carry what it has.
"""

from typing import Any, TypedDict


class Column(TypedDict, total=False):
    type: str
    nullable: bool
    default: str | None
    primary_key: bool
    unique: bool
    references: str | None
    on_delete: str | None
    on_update: str | None
    check: str | None
    literal_values: list[str]
    renamed_from: str
    is_new: bool


class Index(TypedDict, total=False):
    columns: list[str]
    unique: bool
    where: str | None
    using: str | None


class Constraint(TypedDict, total=False):
    type: str
    expression: str | None
    columns: list[str] | None


class Table(TypedDict, total=False):
    columns: dict[str, Column]
    primary_key: list[str]
    indexes: dict[str, Index]
    constraints: dict[str, Constraint]
    renamed_from: str


class Operation(TypedDict):
    op: str
    table: str
    details: dict[str, Any]


class Ambiguity(TypedDict, total=False):
    type: str
    table: str
    from_column: str
    to_column: str
    column: str
    confidence: float
    message: str


class DiffResult(TypedDict):
    operations: list[Operation]
    dependencies: dict[int, list[int]]
    execution_order: list[int]
    ambiguities: list[Ambiguity]


def operation(op: str, table: str, details=None) -> Operation:
    """A single DDL operation (section 4.6). `op` is the discriminator; `details` carries
    op-specific data."""
    return {"op": op, "table": table, "details": details or {}}


def diff_result(operations, dependencies, execution_order, ambiguities) -> DiffResult:
    """The result of a schema diff (section 4.7)."""
    return {
        "operations": operations,
        "dependencies": dependencies,
        "execution_order": execution_order,
        "ambiguities": ambiguities,
    }
