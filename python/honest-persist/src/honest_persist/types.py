"""The types and vocabularies this slice of honest-persist needs, as data.

This pilot slice realizes three pure leaf functions of the declaration: `engine_of`, `worth_retrying`
and `budget_spent`. Between them they read two closed vocabularies and build the framework's canonical
fault, so those three shapes are defined here and nothing else.

The `Fault` record is honest-type's canonical fault (honest-type section 12-13), not a second shape:
honest-persist imports honest-type's `fault` constructor and `is_fault` recognizer and re-exports them,
so a fault built anywhere in this package is the same reserved-`is_err` dict every Honest module builds.

`ENGINES` and `FAULT_CATEGORIES` are the two vocabularies as data — a closed word-to-meaning table
each, copied field for field from the declaration's `engines` and `fault_categories` sets. A vocabulary
in the Honest Framework is a closed set of words; here that set is the dict's keys, and the values are
the declaration's own glosses, kept so a reader of the code meets the same words a reader of the .hd does.
"""

from typing import TypedDict

from honest_type import Fault, fault
from honest_type import is_fault as _ht_is_fault


def is_fault(value):
    """Recognize a Fault within honest-persist's bare unions (honest-type sections 12-13).

    honest-persist's return unions carry bare non-dict members — a WriteOutcome is `int | Fault`, an
    Answer is `Rows | int | bool | NOTHING | Fault` — so the recognizer has to be total over a value
    that may be an int, a float, a bool, None or a list, not only the two-dict unions honest-type's own
    `is_fault` trusts. A fault is a dict carrying honest-type's reserved `is_err` tag (or the legacy
    `code`); nothing else is. This is the bare-union recognizer at the type boundary, not a defensive
    interior re-check: the union genuinely admits non-dict members and a recognizer must decide them."""
    return isinstance(value, dict) and _ht_is_fault(value)


def refused(code, message, detail):
    """A refused Fault (honest-persist overloads honest-type's `category` with its four retry classes;
    `refused` is the request-is-wrong class a retry never helps). The five-field canonical record, built
    through honest-type's own `fault` constructor so it carries the reserved `is_err` tag."""
    return fault(code, message, "refused", [], detail)


def no_match(table, looked_for, rows, reason, detail):
    """A lookup that matched nothing (declaration `type NoMatch`). A different failure from a Fault and
    answered differently: a key no row holds can never mean "try again", so it carries no retry category.
    `table` names which of the five tables was read, `looked_for` the key(s) that arrived, `rows` every
    key the table holds, `reason` whether a key arrived and missed or none arrived, `detail` the caller's
    own writing the key came out of."""
    return {"table": table, "looked_for": looked_for, "rows": rows, "reason": reason, "detail": detail}


def is_no_match(value):
    """Recognize a NoMatch, kept apart from a Fault: it carries `table` and `reason` and no `is_err`."""
    return isinstance(value, dict) and "reason" in value and "table" in value and "is_err" not in value


# --- the closed vocabularies, as data (declaration: the `set`/`vocabulary` lines) -------------------
# The read half and the write half of the asking words (declaration `set readings`, `set writings`).
READINGS = frozenset({
    "all", "one", "first", "page", "distinct", "exists",
    "count", "sum", "average", "smallest", "largest", "count_distinct",
})
WRITINGS = frozenset({"add", "change", "change_all", "remove", "remove_all", "replace"})
WANTED = READINGS | WRITINGS

# The fifteen ways to narrow (declaration `set operators`).
OPERATORS = frozenset({
    "eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "between",
    "like", "contains", "startswith", "endswith", "is_null", "is_not_null",
})

# The four spellings (declaration `set grammars`).
GRAMMARS = frozenset({"pseudo_sql", "django", "prisma", "sqlalchemy"})

# Which way an order sorts (declaration `set directions`).
DIRECTIONS = frozenset({"ascending", "descending"})

# Every schema change the differ can emit (declaration `set operation_kinds`).
OPERATION_KINDS = frozenset({
    "create_table", "drop_table", "add_column", "drop_column", "alter_column",
    "rename_column", "rename_table", "create_index", "drop_index", "create_view",
    "drop_view", "refresh_view", "insert_enum_values", "remove_enum_values",
})

# What shape a caller wants its rows back in (declaration `set shapings`).
SHAPINGS = frozenset({"dictionaries", "objects"})

# How many values a comparison puts beside its symbol (declaration `set value_shapes`).
VALUE_SHAPES = frozenset({"one", "list", "range", "pattern", "none"})

# The things the three engines disagree about (declaration `set features`).
FEATURES = frozenset({"materialized_view", "check_constraint", "partial_index", "enum", "range_type"})

# How far back a failed migration rolls (declaration `set migration_modes`).
MIGRATION_MODES = frozenset({"all_or_nothing", "per_operation"})

# How a driver wants the values handed to it (declaration `set parameter_styles`).
PARAMETER_STYLES = frozenset({"named", "positional"})

# What the scheduler does after one run (declaration `set disposition_kinds`).
DISPOSITION_KINDS = frozenset({"continue", "retry_after", "stop"})

# What the driver of the retry schedule does after one step (declaration `set retry_dispositions`).
RETRY_DISPOSITIONS = frozenset({"run", "landed", "give_up_contention", "give_up_logical"})

# What happens to your data at exit (declaration `set shutdowns`).
SHUTDOWNS = frozenset({"exit_immediately", "replicate_then_exit"})

# Every table in this package read by a key a caller supplied (declaration `set lookup_tables`).
LOOKUP_TABLES = frozenset({"grammars", "method_names", "asking_words", "operators", "engines"})

# The two ways a lookup comes back with nothing (declaration `set no_match_reasons`).
NO_MATCH_REASONS = frozenset({"no_row_for_the_key", "no_key_to_look_up"})

# The three engines, and what in a target names each (declaration: `set engines`, spec section 7).
# The keys are the Engine vocabulary — the only three words `engine_of` may name.
ENGINES = {
    "sqlite": "a bare path, or a sqlite scheme",
    "postgresql": "a postgresql or postgres scheme",
    "turso": "a libsql scheme, or a path with a primary",
}

# The four retry decisions a Fault's category carries (declaration: `set fault_categories`, spec 3.1).
# The keys are the FaultCategory vocabulary; `worth_retrying` reads a fault's category against them and
# finds only `conflict` worth another attempt.
FAULT_CATEGORIES = {
    "conflict": "two writers wrote one row; try again",
    "refused": "the request itself is wrong; change it",
    "budget_spent": "retried as many times as allowed",
    "cut_short": "the process was killed before the work finished",
}

# --- schema-declaration vocabularies (declaration: the schema sets; spec section 5) ---
# A vocabulary-typed field is annotated `str` (its word), the way honest-type's Fault carries
# `category: str`; the closed set of words it may hold is one of the constants below. A glossed
# .hd set becomes a dict word-to-meaning the way the pilot kept ENGINES; a bare-word .hd set
# becomes a frozenset.

# What a column may hold, in words no engine uses (declaration `set declared_types`).
DECLARED_TYPES = frozenset({
    "text", "integer", "float", "decimal", "boolean",
    "bytes", "date", "time", "datetime", "uuid", "json",
})

# What happens to a child row when its parent is deleted (declaration `set deletion_rules`):
# refuse the delete, delete the child too, or empty the column.
DELETION_RULES = frozenset({"refuse", "cascade", "set_null"})

# Every rule you can declare about a column or a table (declaration `set constraint_kinds`), kept
# with its glosses the way the pilot kept ENGINES, since the .hd set carries them.
CONSTRAINT_KINDS = {
    "check": "a rule the value must satisfy",
    "primary_key": "the column that names the row",
    "unique": "no two rows share it",
    "length": "how long the value may be",
    "not_null": "the column must hold something",
    "default": "what goes in when a write names no value",
}

# How fresh a materialized view must be, in requirements rather than mechanisms
# (declaration `set freshnesses`).
FRESHNESSES = frozenset({"always current", "current when read", "refreshed when asked"})


# A value a caller passed; the named absence (NOTHING) is None (declaration `type Value`).
Value = str | int | float | bool | None

# Query-layer and honest-utilities records the schema types carry but this batch's three functions
# never read. Their full shapes belong to the query-layer and scheduler batches; each is named here
# as the opaque record kind the .hd gives the field, so the schema types stay field-for-field
# faithful without pulling the query layer forward. A later batch replaces each alias with its real
# TypedDict.
Condition = dict      # declaration `type Condition` (query layer)
Declaration = dict    # declaration `type Declaration` (query layer)
Cadence = dict        # declaration `type Cadence` (honest-utilities, Appendix C)


class Reference(TypedDict):
    """Where a foreign key points and what a delete does to the child (declaration `type Reference`).
    on_delete is one of the DELETION_RULES words."""

    table: str
    column: str
    on_delete: str


class Field(TypedDict):
    """The two facts about one column that its annotation cannot carry (declaration `type Field`),
    said beside the column rather than at the top of the class so a rename is named once. Both are
    the named absence (None) unless the host said otherwise."""

    renamed_from: str | None
    references: Reference | None


class Column(TypedDict):
    """One column: what it is called, what it holds, what it was called before, and where it points
    (declaration `type Column`). declared_type is one of the DECLARED_TYPES words."""

    name: str
    declared_type: str
    renamed_from: str | None
    references: Reference | None


class Index(TypedDict):
    """A declared promise about speed (declaration `type Index`)."""

    name: str
    columns: list[str]
    unique: bool


class Constraint(TypedDict):
    """One declared rule, over a column or a whole table, as data rather than a string (declaration
    `type Constraint`). kind is one of the CONSTRAINT_KINDS words; rule is what a check reads and
    value is the number a length allows or the value a default writes."""

    name: str
    kind: str
    columns: list[str]
    rule: Condition
    value: Value


class Table(TypedDict):
    """One table's columns, indexes and rules (declaration `type Table`)."""

    name: str
    columns: list[Column]
    indexes: list[Index]
    constraints: list[Constraint]


class View(TypedDict):
    """A declared query with a name; it holds a declaration, never a SELECT (declaration `type View`).
    freshness is one of the FRESHNESSES words or the named absence, and a plain view carries no
    cadence; a view asking to be refreshed on a schedule carries both a cadence and an allowance."""

    name: str
    declaration: Declaration
    freshness: str | None
    cadence: Cadence | None
    attempts_allowed: int | None


class Model(TypedDict):
    """Your description of one table, which is the only description there is (declaration `type
    Model`). name is the model name and table is the table name; a target schema names a table by
    `table`, because a live schema read back from a database names it that way too."""

    name: str
    table: str
    columns: list[Column]
    dropping: list[str]
    indexes: list[Index]
    constraints: list[Constraint]


class Declared(TypedDict):
    """The models and views the code declares (declaration `type Declared`)."""

    models: list[Model]
    views: list[View]
    dropping_tables: list[str]
    dropping_views: list[str]


class Schema(TypedDict):
    """Every table and view, live or declared (declaration `type Schema`)."""

    tables: list[Table]
    views: list[View]


__all__ = [
    "Fault", "fault", "is_fault", "refused", "no_match", "is_no_match",
    "ENGINES", "FAULT_CATEGORIES",
    "DECLARED_TYPES", "DELETION_RULES", "CONSTRAINT_KINDS", "FRESHNESSES",
    "READINGS", "WRITINGS", "WANTED", "OPERATORS", "GRAMMARS", "DIRECTIONS",
    "OPERATION_KINDS", "SHAPINGS", "VALUE_SHAPES", "FEATURES", "MIGRATION_MODES",
    "PARAMETER_STYLES", "DISPOSITION_KINDS", "RETRY_DISPOSITIONS", "SHUTDOWNS",
    "LOOKUP_TABLES", "NO_MATCH_REASONS",
    "Value", "Condition", "Declaration", "Cadence",
    "Reference", "Field", "Column", "Index", "Constraint",
    "Table", "View", "Model", "Declared", "Schema",
]
