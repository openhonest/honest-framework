"""engine_of: read a target and name one of the three engines, opening nothing (declaration `engine_of`,
spec section 7).

The engine is read off the target string alone. A target either carries a scheme (`sqlite://...`,
`postgresql://...`, `postgres://...`, `libsql://...`) or is a bare filesystem path that names no scheme.
The scheme is the text before `://`; a target with no `://` names no scheme, and naming no scheme is what
makes a path sqlite (spec 7.1). So the dispatch is a closed scheme-to-engine table with one extra row for
the no-scheme case, read through the if-free `_pick`. A scheme the table holds no row for names no engine
this package ships, which is a refused Fault — not an engine, and not a raise (engine_of opens nothing and
decides whether a target is usable before anything is opened).
"""

from honest_persist._util import _pick, _read_or
from honest_persist.types import fault, no_match, refused

# scheme -> engine. `None` is the no-scheme row: a bare path names no scheme, which is what makes it
# sqlite (spec 7.1). Every value is one of the three Engine vocabulary words.
_SCHEME_ENGINES = {
    None: "sqlite",
    "sqlite": "sqlite",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "libsql": "turso",
}

# The schemes a caller may name, for the no-match fault's message and detail — every key but the
# no-scheme row (None), which is a bare path rather than a scheme a caller types.
_ACCEPTED_SCHEMES = sorted(set(_SCHEME_ENGINES) - {None})

# The scheme a target names, or None when it names none. The scheme is the text before `://`; a target
# with no `://` is a bare path and names no scheme.
_scheme_of = lambda target: _pick("://" in target, lambda: target.split("://", 1)[0], lambda: None)

# The no-match row of the scheme dispatch: a scheme no engine ships a row for. A refused Fault — the
# request itself is wrong, change it — naming the schemes that would have worked and the one that
# arrived, as data a caller reads from `detail` without parsing the message.
_no_engine = lambda target, scheme: fault(
    "unknown_engine",
    f"target {target!r} names scheme {scheme!r}, which no engine ships a row for; "
    f"name one of the schemes {_ACCEPTED_SCHEMES}, or a bare path for sqlite",
    "refused",
    [],
    {"accepted": _ACCEPTED_SCHEMES, "arrived": scheme, "target": target},
)


def engine_of(target):
    """Name the engine a target is on, opening nothing: a bare path or a sqlite scheme is sqlite, a
    postgresql or postgres scheme is postgresql, a libsql scheme is turso. A scheme no engine ships a
    row for comes back as a refused Fault."""
    scheme = _scheme_of(target)
    return _read_or(_SCHEME_ENGINES, scheme, lambda: _no_engine(target, scheme))


# --- the per-engine tables, data an operator reads (declaration, spec sections 6-7) -----------------
# Each hands back one engine's own row by subscript on a vocabulary-typed argument, which the Engine
# vocabulary bounds at construction, so the interior trusts the contract (P14). The laws drive sqlite.

_TRANSACTING = {
    "turso": {"begin": "BEGIN CONCURRENT", "parameters": "positional", "commits": True},
    "sqlite": {"begin": "BEGIN IMMEDIATE", "parameters": "positional", "commits": True},
    "postgresql": {"begin": "", "parameters": "positional", "commits": False},
}

_THREE_ENGINES_FROM_TRANSACTING = sorted(_TRANSACTING)

# The no-match row for a per-engine table read by the Engine vocabulary (P16): the key is bounded to the
# three engines at construction, so a miss is a program bug, reported as a refused Fault naming the
# engines there are and the one that arrived rather than a bare KeyError.
_no_engine_row = lambda engine: fault(
    "no_such_engine",
    f"no engine here is called {engine!r}; this package ships {_THREE_ENGINES_FROM_TRANSACTING}",
    "server",
    [],
    {"accepted": _THREE_ENGINES_FROM_TRANSACTING, "arrived": engine},
)


def how_to_write(engine):
    """What one engine needs around a write (declaration how_to_write): the statement that opens a
    transaction, how values go to the driver, and whether there is a commit to call."""
    return _read_or(_TRANSACTING, engine, lambda: _no_engine_row(engine))


_MIGRATION_MODES = {"sqlite": "all_or_nothing", "postgresql": "all_or_nothing", "turso": "all_or_nothing"}


def how_to_migrate(engine):
    """How far back a failed migration rolls on this engine (declaration how_to_migrate)."""
    return _read_or(_MIGRATION_MODES, engine, lambda: _no_engine_row(engine))


# One engine's conflict-retry declaration (declaration how_to_retry, spec 7.7). `bound` is how many
# attempts the boundary makes before typing the failure as contention; it lives here, never as a loop
# literal, because under contention it is the bound that decides how many writes land.
_RETRY_POLICIES = {
    "sqlite": {"retryable": ["SQLITE_BUSY", "SQLITE_LOCKED"], "bound": 3, "verified_at_contention": 8},
    "turso": {"retryable": ["Write-write conflict", "SQLITE_BUSY"], "bound": 5, "verified_at_contention": 8},
    "postgresql": {"retryable": ["SerializationError", "DeadlockDetectedError"], "bound": 5, "verified_at_contention": 16},
}


def how_to_retry(engine):
    """This engine's conflict-retry declaration: which driver rejections mean contention on it, the
    attempt bound, and the contention level the bound was verified at (declaration how_to_retry)."""
    return _read_or(_RETRY_POLICIES, engine, lambda: _no_engine_row(engine))


_CARRYING_NONE = {
    "columns": False, "indexes": False, "constraints": False,
    "copying": False, "values": False, "renamed_to": False, "view": False,
}

# One row of the operations table, saying which fields it fills and the rest false.
_filling = lambda named: {**_CARRYING_NONE, **named}


_CARRIES = {
    "create_table": _filling({"columns": True, "constraints": True, "indexes": True}),
    "drop_table": dict(_CARRYING_NONE),
    "add_column": _filling({"columns": True}),
    "drop_column": _filling({"columns": True}),
    "alter_column": _filling({"columns": True, "constraints": True, "indexes": True, "copying": True}),
    "rename_column": _filling({"renamed_to": True, "columns": True}),
    "rename_table": _filling({"renamed_to": True, "columns": True, "constraints": True}),
    "create_index": _filling({"indexes": True}),
    "drop_index": _filling({"indexes": True}),
    "create_view": _filling({"view": True}),
    "drop_view": _filling({"view": True}),
    "refresh_view": _filling({"view": True}),
    "insert_enum_values": _filling({"values": True}),
    "remove_enum_values": _filling({"values": True}),
}


_OPERATION_KINDS_CARRIED = sorted(_CARRIES)

# The no-match row for the operations table read by the OperationKind vocabulary (P16): the key is
# bounded to the fourteen kinds at construction, so a miss is a program bug, reported as a refused Fault
# naming the kinds there are and the one that arrived rather than a bare KeyError.
_no_kind_row = lambda kind: fault(
    "no_such_operation_kind",
    f"no schema change here is called {kind!r}; this package emits {_OPERATION_KINDS_CARRIED}",
    "server",
    [],
    {"accepted": _OPERATION_KINDS_CARRIED, "arrived": kind},
)


def what_an_operation_carries(kind):
    """Which fields one kind of schema change fills (declaration what_an_operation_carries)."""
    return _read_or(_CARRIES, kind, lambda: _no_kind_row(kind))


_A_MATERIALIZED_VIEW_BUILT = (
    "created: a table holding the rows, the triggers that keep it current, and a registry row naming it "
    "a view; dropped: the triggers, then the registry row, then the table; recognized: the inspector "
    "asks the registry, so the table reads back as the view it stands for"
)
_AN_ENUM_BUILT = (
    "created: a lookup table holding the permitted values and a foreign key from the column to it; "
    "dropped: the foreign key with its column, then the lookup table; recognized: the inspector reads "
    "the lookup table's rows as the values the column permits"
)
_A_RANGE_BUILT = (
    "created: a column for the lower bound, a column for the upper bound, and a check that the lower is "
    "not above the upper; dropped: the check, then both columns; recognized: the inspector reads the "
    "pair together with the check and reports one range column"
)
_NATIVE = ""

_CAPABILITIES = {
    ("postgresql", "materialized_view"): (True, _NATIVE),
    ("sqlite", "materialized_view"): (False, _A_MATERIALIZED_VIEW_BUILT),
    ("turso", "materialized_view"): (False, _A_MATERIALIZED_VIEW_BUILT),
    ("postgresql", "check_constraint"): (True, _NATIVE),
    ("sqlite", "check_constraint"): (True, _NATIVE),
    ("turso", "check_constraint"): (True, _NATIVE),
    ("postgresql", "partial_index"): (True, _NATIVE),
    ("sqlite", "partial_index"): (True, _NATIVE),
    ("turso", "partial_index"): (True, _NATIVE),
    ("postgresql", "enum"): (True, _NATIVE),
    ("sqlite", "enum"): (False, _AN_ENUM_BUILT),
    ("turso", "enum"): (False, _AN_ENUM_BUILT),
    ("postgresql", "range_type"): (True, _NATIVE),
    ("sqlite", "range_type"): (False, _A_RANGE_BUILT),
    ("turso", "range_type"): (False, _A_RANGE_BUILT),
}


def capability_of(engine, feature):
    """What this engine does about this feature: has it natively, or what builds it where it does not
    (declaration capability_of). A fresh dict every call, so a caller cannot edit the shared table."""
    native, built_from = _CAPABILITIES[(engine, feature)]
    return {"native": native, "built_from": built_from}


# --- how one engine writes one comparison (declaration how_to_compare) -------------------------------
_COMPARISONS = {
    "eq": {"symbol": "=", "shape": "one", "wraps": "", "ignoring_case": ""},
    "ne": {"symbol": "!=", "shape": "one", "wraps": "", "ignoring_case": ""},
    "lt": {"symbol": "<", "shape": "one", "wraps": "", "ignoring_case": ""},
    "lte": {"symbol": "<=", "shape": "one", "wraps": "", "ignoring_case": ""},
    "gt": {"symbol": ">", "shape": "one", "wraps": "", "ignoring_case": ""},
    "gte": {"symbol": ">=", "shape": "one", "wraps": "", "ignoring_case": ""},
    "in": {"symbol": "IN", "shape": "list", "wraps": "", "ignoring_case": ""},
    "not_in": {"symbol": "NOT IN", "shape": "list", "wraps": "", "ignoring_case": ""},
    "between": {"symbol": "BETWEEN", "shape": "range", "wraps": "", "ignoring_case": ""},
    "like": {"symbol": "LIKE", "shape": "one", "wraps": "{}", "ignoring_case": "LIKE"},
    "contains": {"symbol": "LIKE", "shape": "pattern", "wraps": "%{}%", "ignoring_case": "LIKE"},
    "startswith": {"symbol": "LIKE", "shape": "pattern", "wraps": "{}%", "ignoring_case": "LIKE"},
    "endswith": {"symbol": "LIKE", "shape": "pattern", "wraps": "%{}", "ignoring_case": "LIKE"},
    "is_null": {"symbol": "IS NULL", "shape": "none", "wraps": "", "ignoring_case": ""},
    "is_not_null": {"symbol": "IS NOT NULL", "shape": "none", "wraps": "", "ignoring_case": ""},
}

_CASE_WORD = {
    "postgresql": dict.fromkeys(("like", "contains", "startswith", "endswith"), "ILIKE"),
    "sqlite": {},
    "turso": {},
}

_THREE_ENGINES = sorted(_CASE_WORD)
_FIFTEEN_OPERATORS = sorted(_COMPARISONS)

# The no-match row for the comparisons table read by the Operator vocabulary (P16): the key is bounded
# to the fifteen operators at construction, so a miss is a program bug, reported as a refused Fault
# naming the operators there are and the one that arrived rather than a bare KeyError.
_no_operator_row = lambda operator: fault(
    "no_such_operator",
    f"no comparison here is called {operator!r}; this package writes {_FIFTEEN_OPERATORS}",
    "server",
    [],
    {"accepted": _FIFTEEN_OPERATORS, "arrived": operator},
)


def how_to_compare(operator, engine):
    """How this engine writes this comparison (declaration how_to_compare). It names no Fault at all:
    both arguments are vocabularies, so the only two ways it can fail are the two misses, each a NoMatch
    naming the table that had no row."""
    def _comparing_row(operator, engine):
        # The shared comparison row, with this engine's own case word where it has one. Reached only once
        # both vocabularies have matched, so each read is a guaranteed hit; the reads go through _read_or
        # so the subscript is on a local, never on a module dispatch dict by a bare key.
        case_words = _read_or(_CASE_WORD, engine, lambda: {})
        comparison = _read_or(_COMPARISONS, operator, lambda: _no_operator_row(operator))
        said_differently = operator in case_words
        return {
            **comparison,
            "ignoring_case": _pick(
                said_differently,
                lambda: case_words[operator],
                lambda: comparison["ignoring_case"],
            ),
        }

    def _compare_miss(operator, engine):
        # The no-match row: a NoMatch differing by which table missed, an engine the package ships no row
        # for, or an operator this table holds no row for.
        engine_known = engine in _CASE_WORD
        return _pick(
            engine_known,
            lambda: no_match("operators", [operator], _FIFTEEN_OPERATORS, "no_row_for_the_key",
                             f"operator {operator!r} on engine {engine!r}"),
            lambda: no_match("engines", [engine], _THREE_ENGINES, "no_row_for_the_key",
                             f"engine {engine!r}"),
        )

    written_down = engine in _CASE_WORD and operator in _COMPARISONS
    return _pick(written_down, lambda: _comparing_row(operator, engine),
                 lambda: _compare_miss(operator, engine))


# --- how one engine writes one schema change (declaration how_to_spell) ------------------------------
# A change one statement carries out, on an engine that alters in place.
_one_statement = lambda statement: {"statements": [statement], "rebuilds": False, "commits_between": False}


_SPELL_SAME = {
    "create_table": _one_statement("CREATE TABLE"),
    "drop_table": _one_statement("DROP TABLE"),
    "add_column": _one_statement("ALTER TABLE ADD COLUMN"),
    "drop_column": _one_statement("ALTER TABLE DROP COLUMN"),
    "alter_column": _one_statement("ALTER TABLE ALTER COLUMN"),
    "rename_column": _one_statement("ALTER TABLE RENAME COLUMN"),
    "rename_table": _one_statement("ALTER TABLE RENAME TO"),
    "create_index": _one_statement("CREATE INDEX"),
    "drop_index": _one_statement("DROP INDEX"),
    "create_view": _one_statement("CREATE VIEW"),
    "drop_view": _one_statement("DROP VIEW"),
    "insert_enum_values": _one_statement("INSERT INTO"),
    "remove_enum_values": _one_statement("DELETE FROM"),
}

_A_REBUILD = {
    "statements": ["CREATE TABLE", "INSERT INTO SELECT FROM", "DROP TABLE", "ALTER TABLE RENAME TO"],
    "rebuilds": True,
    "commits_between": False,
}
_A_COLUMN_BY_COPYING = {
    "statements": ["ALTER TABLE ADD COLUMN", "UPDATE SET", "ALTER TABLE DROP COLUMN"],
    "rebuilds": False,
    "commits_between": True,
}
_A_TABLE_BY_COPYING = {
    "statements": ["CREATE TABLE", "INSERT INTO SELECT FROM", "DROP TABLE"],
    "rebuilds": True,
    "commits_between": True,
}

_SPELL_LOCAL = {
    "sqlite": {"alter_column": _A_REBUILD},
    "turso": {"alter_column": _A_REBUILD},
    "postgresql": {},
}
_SPELL_REPLICA = {
    "sqlite": {"alter_column": _A_REBUILD},
    "postgresql": {},
    "turso": {
        "rename_column": _A_COLUMN_BY_COPYING,
        "rename_table": _A_TABLE_BY_COPYING,
        "drop_column": _SPELL_SAME["drop_column"],
    },
}
_SPELL_OWN = {False: _SPELL_LOCAL, True: _SPELL_REPLICA}

_OUT_OF_REACH_REPLICA = {"sqlite": frozenset(), "postgresql": frozenset(), "turso": frozenset({"alter_column"})}
_OUT_OF_REACH_LOCAL = {"sqlite": frozenset(), "postgresql": frozenset(), "turso": frozenset()}
_OUT_OF_REACH = {False: _OUT_OF_REACH_LOCAL, True: _OUT_OF_REACH_REPLICA}

_SPELL_KINDS = sorted(_SPELL_SAME)

_spell_cannot_reach = lambda kind, engine: refused(
    "change_cannot_reach_primary",
    f"a {kind} on {engine} cannot reach the primary: {engine} alters a column by rebuilding the "
    f"table, and the rename that ends a rebuild runs locally and sends nothing. Declare the change "
    f"as a new column and a dropping line rather than as a change to the column that is there.",
    {"kind": kind, "engine": engine},
)

_spell_no_row = lambda kind, engine: refused(
    "no_spelling_for_change",
    f"there is no rule for writing {kind!r} on {engine!r}; this library emits "
    f"{len(_SPELL_SAME)} kinds of schema change and that is not one of them (accepted {_SPELL_KINDS})",
    {"accepted": _SPELL_KINDS, "arrived": kind, "engine": engine},
)

_spell_no_engine = lambda kind, engine: refused(
    "no_such_engine",
    f"no engine here is called {engine!r}; this package ships {_THREE_ENGINES}",
    {"accepted": _THREE_ENGINES, "arrived": engine},
)


def how_to_spell(kind, engine, replicating):
    """How this engine writes this schema change, here, on this database (declaration how_to_spell).
    `replicating` is part of the question because a statement that runs on the local copy is not a
    statement that reaches the primary."""
    def _spell_written_down(kind, engine, replicating):
        def _spell_row(kind, engine, replicating):
            # The shared row, or this engine's own where it has one. Reached only once how_to_spell has
            # matched both vocabularies, so each read is a guaranteed hit; the reads go through _read_or
            # so the subscript is on a local, never on a module dispatch dict by a bare key.
            own_by_engine = _read_or(_SPELL_OWN, replicating, lambda: {})
            own = _read_or(own_by_engine, engine, lambda: {})
            return _pick(kind in own, lambda: own[kind],
                         lambda: _read_or(_SPELL_SAME, kind, lambda: _spell_no_row(kind, engine)))

        out_of_reach_by_engine = _read_or(_OUT_OF_REACH, replicating, lambda: {})
        out_of_reach = kind in _read_or(out_of_reach_by_engine, engine, lambda: frozenset())
        return _pick(out_of_reach, lambda: _spell_cannot_reach(kind, engine),
                     lambda: _spell_row(kind, engine, replicating))

    key = (kind in _SPELL_SAME, engine in _SPELL_LOCAL)
    return {
        (True, True): _spell_written_down,
        (True, False): lambda k, e, r: _spell_no_engine(k, e),
        (False, True): lambda k, e, r: _spell_no_row(k, e),
        (False, False): lambda k, e, r: _spell_no_engine(k, e),
    }[key](kind, engine, replicating)


# --- the six questions one engine answers about itself (declaration how_to_inspect) ------------------
_asked = lambda text: {"text": text, "parameters": {}}

_about_table = lambda text: {"text": text, "parameters": {"table": ""}}


_SQLITE_TYPES = {
    "text": "text", "varchar": "text", "char": "text", "clob": "text",
    "integer": "integer", "int": "integer", "bigint": "integer", "smallint": "integer",
    "real": "float", "double": "float", "float": "float",
    "numeric": "decimal", "decimal": "decimal", "boolean": "boolean", "bool": "boolean",
    "blob": "bytes", "date": "date", "time": "time", "datetime": "datetime",
    "timestamp": "datetime", "uuid": "uuid", "json": "json",
}

_POSTGRESQL_TYPES = {
    "text": "text", "character varying": "text", "character": "text", "varchar": "text",
    "integer": "integer", "bigint": "integer", "smallint": "integer",
    "real": "float", "double precision": "float", "numeric": "decimal", "decimal": "decimal",
    "boolean": "boolean", "bytea": "bytes", "date": "date", "time": "time",
    "timestamp": "datetime", "timestamp without time zone": "datetime", "uuid": "uuid",
    "json": "json", "jsonb": "json",
}

_EMPTY_QUESTION = _asked("SELECT name AS name FROM sqlite_master WHERE type = 'table' AND 0 = 1")

_INSPECT_SQLITE = {
    "tables": _asked("SELECT name AS name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"),
    "columns": _about_table(
        "SELECT name AS name, type AS declared_type, \"notnull\" AS must_hold_something, "
        "dflt_value AS starts_at, pk AS is_key FROM pragma_table_info(?)"
    ),
    "indexes": _about_table(
        "SELECT name AS name, \"unique\" AS is_unique, origin AS spelled_out FROM pragma_index_list(?)"
    ),
    "constraints": _about_table(
        "SELECT name AS name, 'in_the_ddl' AS kind, sql AS spelled_out "
        "FROM sqlite_master WHERE type = 'table' AND name = ?"
    ),
    "views": _asked("SELECT name AS name, sql AS spelled_out FROM sqlite_master WHERE type = 'view'"),
    "materialized_views": _EMPTY_QUESTION,
    "types": _SQLITE_TYPES,
}

_INSPECT_TURSO = {
    **_INSPECT_SQLITE,
    "tables": _asked(
        "SELECT name AS name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE 'turso_%'"
    ),
}

_INSPECT_POSTGRESQL = {
    "tables": _asked(
        "SELECT table_name AS name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ),
    "columns": _about_table(
        "SELECT column_name AS name, data_type AS declared_type, "
        "CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS must_hold_something, "
        "column_default AS starts_at, 0 AS is_key "
        "FROM information_schema.columns WHERE table_schema = 'public' AND table_name = $1"
    ),
    "indexes": _about_table(
        "SELECT indexname AS name, CASE WHEN indexdef LIKE 'CREATE UNIQUE%' THEN 1 ELSE 0 END AS is_unique, "
        "indexdef AS spelled_out FROM pg_indexes WHERE schemaname = 'public' AND tablename = $1"
    ),
    "constraints": _about_table(
        "SELECT conname AS name, contype::text AS kind, pg_get_constraintdef(oid) AS spelled_out "
        "FROM pg_constraint WHERE conrelid = to_regclass($1)"
    ),
    "views": _asked(
        "SELECT table_name AS name, view_definition AS spelled_out FROM information_schema.views "
        "WHERE table_schema = 'public'"
    ),
    "materialized_views": _asked(
        "SELECT matviewname AS name FROM pg_matviews WHERE schemaname = 'public'"
    ),
    "types": _POSTGRESQL_TYPES,
}

_INSPECTORS = {"sqlite": _INSPECT_SQLITE, "turso": _INSPECT_TURSO, "postgresql": _INSPECT_POSTGRESQL}


def how_to_inspect(engine):
    """The six questions this engine answers about itself and its own word for each thing a column can
    hold (declaration how_to_inspect)."""
    return _read_or(_INSPECTORS, engine, lambda: _no_engine_row(engine))


# --- refuse a setting this engine cannot use (declaration refuse_unusable_settings) ------------------
_USABLE_SETTINGS = {
    "sqlite": frozenset({"busy_timeout_s"}),
    "postgresql": frozenset(),
    "turso": frozenset({"busy_timeout_s", "primary"}),
}


def refuse_unusable_settings(engine, settings):
    """Refuse a setting this engine cannot use, rather than ignoring it (declaration
    refuse_unusable_settings); hand back the rest unchanged."""
    usable = _read_or(_USABLE_SETTINGS, engine, lambda: frozenset())
    unusable = list(filter(lambda name: name not in usable, settings))
    return _pick(
        unusable == [],
        lambda: settings,
        lambda: refused(
            "unusable_setting",
            f"you opened a {engine} database and set {', '.join(unusable)}; {engine} has no use for it, "
            f"so write the call again without it",
            {"engine": engine, "unusable": unusable},
        ),
    )
