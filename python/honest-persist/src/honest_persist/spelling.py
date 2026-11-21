"""The schema half's compiler: spell_operation, spell_view, mechanism_for.

spell_operation turns one schema change into the statements that carry it out on one engine; spell_view
writes the SELECT a declared view stands for; mechanism_for picks the mechanism that gives a materialized
view the freshness asked for. Ported from declaro-persistum, adapted to honest-persist's bare-union Fault
and NoMatch records: a NoMatch from how_to_spell or compile_statement travels out as it stands.
"""

from honest_persist._compile import compile_statement
from honest_persist._util import _pick, _read_or
from honest_persist.engines import how_to_spell
from honest_persist.types import READINGS, is_fault, is_no_match, no_match, refused

NOTHING = None
_THREE_ENGINES = ("postgresql", "sqlite", "turso")


# Quote one identifier with ANSI double quotes.
_quoted = lambda name: '"' + name.replace('"', '""') + '"'


# Identifier quoting does not vary by engine: SQLite, PostgreSQL and Turso all quote an
# identifier with ANSI double quotes, so there is no per-engine dispatch here, only _quoted.
_SQLITE_TYPES = {
    "uuid": "TEXT", "text": "TEXT", "json": "TEXT", "date": "TEXT", "time": "TEXT", "datetime": "TEXT",
    "decimal": "TEXT", "integer": "INTEGER", "boolean": "INTEGER", "float": "REAL", "bytes": "BLOB",
}
_POSTGRESQL_TYPES = {
    "uuid": "uuid", "text": "text", "json": "jsonb", "date": "date", "time": "time",
    "datetime": "timestamptz", "decimal": "numeric", "integer": "integer", "boolean": "boolean",
    "float": "double precision", "bytes": "bytea",
}
_TYPES = {"sqlite": _SQLITE_TYPES, "postgresql": _POSTGRESQL_TYPES, "turso": _SQLITE_TYPES}


def _the_first_fault_or(pieces, build):
    faults = list(filter(_is_refusal, pieces))
    return _OR_BUILD[faults != []](faults, build)


_OR_BUILD = {True: lambda faults, _build: faults[0], False: lambda _faults, build: build()}


_is_refusal = lambda piece: is_fault(piece) or is_no_match(piece)


# A column is declared a type this package has no storage class for.
_no_such_type = lambda declared, engine: refused(
    "no_storage_class",
    f"a column is declared {declared!r}, and this package has no {engine} storage class "
    f"for it", {"declared": declared, "engine": engine})


def type_spelled(declared, engine):
    table = _read_or(_TYPES, engine, lambda: {})
    wanted = declared.lower()
    return _TYPE_KNOWN[wanted in table](declared, engine, table, wanted)


_TYPE_KNOWN = {
    True: lambda _declared, _engine, table, wanted: table[wanted],
    False: lambda declared, engine, _table, _wanted: _no_such_type(declared, engine),
}


_BOOLEAN_LITERAL = {
    "sqlite": {True: "1", False: "0"}, "postgresql": {True: "TRUE", False: "FALSE"},
    "turso": {True: "1", False: "0"},
}


# A text default is a bare parenthesised expression passed through, or a quoted string literal.
_text_literal = lambda value, _engine: _pick(
    value.startswith("(") and value.endswith(")"),
    lambda: value, lambda: "'" + value.replace("'", "''") + "'")

_LITERAL = {
    str: _text_literal,
    int: lambda value, _engine: str(value),
    float: lambda value, _engine: repr(value),
    bool: lambda value, engine: _read_or(_BOOLEAN_LITERAL, engine, lambda: {True: "1", False: "0"})[value],
    type(NOTHING): lambda _value, _engine: "NULL",
}


_literal = lambda value, engine: _LITERAL_KNOWN[type(value) in _LITERAL](value, engine)


_LITERAL_KNOWN = {
    True: lambda value, engine: _LITERAL[type(value)](value, engine),
    False: lambda value, engine: refused("bad_default",
                                          f"a default of {value!r} is a {type(value).__name__}",
                                          {"type": type(value).__name__}),
}


def _default_clause(value, engine):
    literal = _literal(value, engine)
    return _the_first_fault_or([literal], lambda: f"DEFAULT {literal}")


_STANDARD_ON_DELETE = {"refuse": "ON DELETE NO ACTION", "cascade": "ON DELETE CASCADE", "set_null": "ON DELETE SET NULL"}


_REF_KNOWN = {
    True: lambda reference, _engine, quote, declared: (
        f"REFERENCES {quote(reference['table'])}({quote(reference['column'])}) {_read_or(_STANDARD_ON_DELETE, declared, lambda: '')}"
    ),
    False: lambda reference, engine, _quote, declared: refused(
        "bad_on_delete", f"a column points at {reference['table']} and declares {declared!r}",
        {"on_delete": declared}),
}


_its_own = lambda column, constraints, kind: list(
    filter(lambda c: c["kind"] == kind and column["name"] in c["columns"], constraints))


_COLUMN_CLAUSE = {
    "not_null": lambda _constraint, _engine: "NOT NULL",
    "default": lambda constraint, engine: _default_clause(constraint["value"], engine),
}


def _definition(column, constraints, engine):
    def _reference_clause(reference, engine):
        quote = _quoted
        declared = reference["on_delete"]
        return _REF_KNOWN[declared in _STANDARD_ON_DELETE](reference, engine, quote, declared)

    pieces = [
        _quoted(column["name"]),
        type_spelled(column["declared_type"], engine),
        *[
            clause(constraint, engine)
            for kind, clause in _COLUMN_CLAUSE.items()
            for constraint in _its_own(column, constraints, kind)
        ],
        *[_reference_clause(reference, engine) for reference in filter(None, [column["references"]])],
    ]
    return _the_first_fault_or(pieces, lambda: " ".join(filter(None, pieces)))


def _over_its_columns(word):
    def spelled(constraint, engine):
        quote = _quoted
        named = [quote(column) for column in constraint["columns"]]
        return _OVER[named == []](constraint, engine, word, named)

    return spelled


_OVER = {
    False: lambda constraint, engine, word, named: (
        f"CONSTRAINT {_quoted(constraint['name'])} {word} ({', '.join(named)})"
    ),
    True: lambda constraint, _engine, word, _named: refused(
        "empty_constraint", f"the constraint {constraint['name']!r} names no column", {}),
}


_flat_check = lambda constraint, engine: refused(
    "check_unsupported", f"the constraint {constraint['name']!r} is a check this reduced "
    "speller does not write", {})


_CONSTRAINT_CLAUSE = {
    "check": _flat_check,
    "primary_key": _over_its_columns("PRIMARY KEY"),
    "unique": _over_its_columns("UNIQUE"),
    "length": lambda constraint, _engine: refused("length_unsupported", "length not spelled here", {}),
}

_COLUMN_KINDS = frozenset({"not_null", "default"})


_CONSTRAINT_KNOWN = {
    True: lambda constraint, engine, kind: _read_or(_CONSTRAINT_CLAUSE, kind, lambda: _flat_check)(constraint, engine),
    False: lambda constraint, _engine, kind: refused(
        "no_such_constraint_kind", f"the constraint {constraint['name']!r} is a {kind!r}", {"kind": kind}),
}


_statement = lambda text, values: {
    "text": text, "parameters": {f"p{position}": value for position, value in enumerate(values, start=1)}}


def _table_body(operation, engine):
    def _constraint_clause(constraint, engine):
        kind = constraint["kind"]
        return _CONSTRAINT_KNOWN[kind in _CONSTRAINT_CLAUSE](constraint, engine, kind)

    constraints = operation["constraints"]
    pieces = [
        *[_definition(column, constraints, engine) for column in operation["columns"]],
        *[
            _constraint_clause(constraint, engine)
            for constraint in filter(lambda c: c["kind"] not in _COLUMN_KINDS, constraints)
        ],
    ]
    return _the_first_fault_or(pieces, lambda: ", ".join(pieces))


def _index_statement(index, table, engine):
    quote = _quoted
    unique = {True: "UNIQUE ", False: ""}[index["unique"]]
    columns = ", ".join(quote(column) for column in index["columns"])
    return _statement(f"CREATE {unique}INDEX {quote(index['name'])} ON {quote(table)} ({columns})", [])


_empty_handed = lambda operation, engine, field: refused(
    "empty_field", f"a {operation['kind']} on {operation['table']} was handed an empty {field}",
    {"field": field})


_carrying = lambda operation, engine, field, build: _CARRYING[operation[field] == []](
    operation, engine, field, build)


_CARRYING = {
    True: lambda operation, engine, field, _build: _empty_handed(operation, engine, field),
    False: lambda _operation, _engine, _field, build: build(),
}


def _create_table(operation, engine):
    def spelled():
        body = _table_body(operation, engine)
        return _the_first_fault_or([body], lambda: [
            _statement(f"CREATE TABLE {_quoted(operation['table'])} ({body})", []),
            *[_index_statement(index, operation["table"], engine) for index in operation["indexes"]],
        ])

    return _carrying(operation, engine, "columns", spelled)


_drop_table = lambda operation, engine: [_statement(f"DROP TABLE {_quoted(operation['table'])}", [])]


_NAMED = {
    True: lambda _operation, _engine, _wanted, found: found[0],
    False: lambda operation, engine, wanted, _found: refused(
        "no_such_column", f"a {operation['kind']} on {operation['table']} names {wanted!r}", {}),
}


def _add_column(operation, engine):
    def spelled():
        def _named_column(operation, engine):
            wanted = operation["column"]
            found = list(filter(lambda c: c["name"] == wanted, operation["columns"]))
            return _NAMED[found != []](operation, engine, wanted, found)

        column = _named_column(operation, engine)
        definition = _the_first_fault_or([column], lambda: _definition(column, operation["constraints"], engine))
        return _the_first_fault_or([column, definition], lambda: [
            _statement(f"ALTER TABLE {_quoted(operation['table'])} ADD COLUMN {definition}", [])])

    return _carrying(operation, engine, "columns", spelled)


_drop_column_directly = lambda operation, engine: [
    _statement(f"ALTER TABLE {_quoted(operation['table'])} DROP COLUMN {_quoted(operation['column'])}", [])]


_COPY = {
    True: lambda _temporary, _carried, _table: [],
    False: lambda temporary, carried, table: [
        _statement(f"INSERT INTO {temporary} ({carried}) SELECT {carried} FROM {table}", [])],
}


def _rebuild(operation, engine):
    def spelled():
        def _copy(operation, engine):
            quote = _quoted
            carried = ", ".join(quote(column) for column in operation["copying"])
            temporary = quote(f"_honest_persist_tmp_{operation['table']}")
            table = quote(operation["table"])
            return _COPY[operation["copying"] == []](temporary, carried, table)

        quote = _quoted
        table = quote(operation["table"])
        temporary = quote(f"_honest_persist_tmp_{operation['table']}")
        body = _table_body(operation, engine)
        return _the_first_fault_or([body], lambda: [
            _statement(f"DROP TABLE IF EXISTS {temporary}", []),
            _statement(f"CREATE TABLE {temporary} ({body})", []),
            *_copy(operation, engine),
            _statement(f"DROP TABLE {table}", []),
            _statement(f"ALTER TABLE {temporary} RENAME TO {table}", []),
            *[_index_statement(index, operation["table"], engine) for index in operation["indexes"]],
        ])

    return _carrying(operation, engine, "columns", spelled)


_rename_column = lambda operation, engine: [_statement(
    f"ALTER TABLE {_quoted(operation['table'])} RENAME COLUMN {_quoted(operation['column'])} "
    f"TO {_quoted(operation['renamed_to'])}", [])]


_rename_table = lambda operation, engine: [_statement(
    f"ALTER TABLE {_quoted(operation['table'])} RENAME TO {_quoted(operation['renamed_to'])}", [])]


_create_index = lambda operation, engine: [_index_statement(operation["indexes"][0], operation["table"], engine)]


_drop_index = lambda operation, engine: [_statement(f"DROP INDEX {_quoted(operation['indexes'][0]['name'])}", [])]


def _create_view(operation, engine):
    select = spell_view(operation["view"], engine)
    return _the_first_fault_or([select], lambda: [
        _statement(f"CREATE VIEW {_quoted(operation['view']['name'])} AS {select['text']}", [])])


_drop_view = lambda operation, engine: [_statement(f"DROP VIEW {_quoted(operation['view']['name'])}", [])]


_enum_values = lambda verb: lambda operation, engine: [
    _statement(f"{verb} {_quoted(operation['table'])} VALUES (?)", [value])
    for value in operation["values"]]


_SHARED = {
    "create_table": _create_table, "drop_table": _drop_table, "add_column": _add_column,
    "rename_column": _rename_column, "rename_table": _rename_table, "create_index": _create_index,
    "drop_index": _drop_index, "create_view": _create_view, "drop_view": _drop_view,
    "insert_enum_values": _enum_values("INSERT INTO"), "remove_enum_values": _enum_values("DELETE FROM"),
}
_SQLITE_SPELLING = {**_SHARED, "drop_column": _rebuild, "alter_column": _rebuild}
_POSTGRESQL_SPELLING = {**_SHARED, "drop_column": _drop_column_directly, "alter_column": _drop_column_directly}


_it_cannot_reach_primary = lambda operation, engine: how_to_spell(operation["kind"], engine, True)


_TURSO_REPLICATED = {**_SHARED, "drop_column": _drop_column_directly, "alter_column": _it_cannot_reach_primary,
                     "rename_column": _rename_column, "rename_table": _rename_table}

_SPELLING = {
    False: {"sqlite": _SQLITE_SPELLING, "postgresql": _POSTGRESQL_SPELLING, "turso": _SQLITE_SPELLING},
    True: {"sqlite": _SQLITE_SPELLING, "postgresql": _POSTGRESQL_SPELLING, "turso": _TURSO_REPLICATED},
}


# The no-match row for the spelling tables (P16): a kind no table holds a speller for. Reached only
# if how_to_spell let a kind through that _SPELLING has no row for, which the shared key set prevents,
# so it is a program bug reported as a refused Fault rather than a bare KeyError.
_no_spelling_row = lambda operation, engine: refused(
    "no_spelling_for_change",
    f"a {operation['kind']} on {engine} reached the speller with no row to write it",
    {"kind": operation["kind"], "engine": engine})


_spell = lambda operation, engine, replicating: _read_or(
    _read_or(_read_or(_SPELLING, replicating, lambda: {}), engine, lambda: {}),
    operation["kind"], lambda: _no_spelling_row)(operation, engine)


def spell_operation(operation, engine, replicating):
    """Turn one schema change into the statements that carry it out (declaration spell_operation); a
    replicated database is handed a different spelling for the same change. Whether this pair has a rule
    is asked of how_to_spell, whose Fault or NoMatch travels out of here unchanged."""
    written = how_to_spell(operation["kind"], engine, replicating)
    return _OR_THE_REFUSAL[_is_refusal(written)](written, operation, engine, replicating)


_OR_THE_REFUSAL = {
    True: lambda written, _operation, _engine, _replicating: written,
    False: lambda _written, operation, engine, replicating: _spell(operation, engine, replicating),
}


# --- spell_view (declaration spell_view) -------------------------------------------------------------
_A_VIEW_MAY_STAND_FOR = {
    "postgresql": frozenset(READINGS), "sqlite": frozenset(READINGS), "turso": frozenset(READINGS),
}


_no_such_engine_view = lambda view, engine: refused(
    "no_such_engine", f"the view {view['name']!r} was handed to be spelled for {engine!r}",
    {"accepted": list(_THREE_ENGINES), "arrived": engine})


_not_a_question = lambda view, engine: refused(
    "view_not_a_question",
    f"the view {view['name']!r} stands for a declaration that asks to "
    f"{view['declaration']['wanted']}", {})


# answer is a Fault here (not a Statement, not a NoMatch), so it carries honest-type's code,
# message and detail fields; the interior trusts that contract (P14) and reads them by subscript.
_named_view_fault = lambda view, engine, answer: refused(
    answer["code"],
    f"the view {view['name']!r} cannot be spelled for {engine}: {answer['message']}",
    answer["detail"])


def _compiled_view(view, engine):
    answer = compile_statement(view["declaration"], engine)
    return _VIEW_CAME_BACK["text" in answer](view, engine, answer)


_VIEW_CAME_BACK = {
    True: lambda _view, _engine, answer: answer,
    False: lambda view, engine, answer: _VIEW_REFUSAL[is_no_match(answer)](view, engine, answer),
}
_VIEW_REFUSAL = {
    True: lambda _view, _engine, answer: answer,
    False: _named_view_fault,
}


_when_stands_for_a_question = lambda view, engine: _pick(
    view["declaration"]["wanted"] in _read_or(_A_VIEW_MAY_STAND_FOR, engine, lambda: frozenset()),
    lambda: _compiled_view(view, engine), lambda: _not_a_question(view, engine))


_VIEW_ENGINE = {True: _when_stands_for_a_question, False: _no_such_engine_view}


def spell_view(view, engine):
    """Write the SELECT a declared view stands for, on one engine (declaration spell_view). A view holds
    a declaration, so it compiles through the same card a caller's question does; a NoMatch from the
    compiler travels out as it stands."""
    return _VIEW_ENGINE[engine in _THREE_ENGINES](view, engine)


# --- mechanism_for (declaration mechanism_for) -------------------------------------------------------
_OFFERS = {(True, True): "native", (True, False): "native", (False, True): "built", (False, False): "nothing"}

_MECHANISM = {
    ("native", "always current"): {"kind": "create_view", "is": "a materialized view the engine holds"},
    ("native", "current when read"): {"kind": "create_view", "is": "a materialized view, refreshed on read"},
    ("native", "refreshed when asked"): {"kind": "create_view", "is": "a materialized view, refreshed on ask"},
    ("built", "always current"): {"kind": "create_table", "is": "a table and triggers that keep it current"},
    ("built", "current when read"): {"kind": "create_table", "is": "a table rebuilt before each read"},
    ("built", "refreshed when asked"): {"kind": "create_table", "is": "a table rebuilt when a caller asks"},
}
_DECLARED_FRESHNESSES = tuple(dict.fromkeys(freshness for _offers, freshness in _MECHANISM))


def _mechanism_operations(freshness, engine, capability):
    offers = _OFFERS[(capability["native"], bool(capability["built_from"].strip()))]
    mechanism = _MECHANISM[(offers, freshness)]
    return [{"kind": mechanism["kind"], "table": "", "column": None, "columns": [], "indexes": [],
             "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None,
             "destroys": False, "detail": {"is": mechanism["is"], "for_freshness": freshness,
                                           "on_engine": engine, "built_from": capability["built_from"]}}]


_refuse_mechanism_engine = lambda freshness, engine, _capability: refused(
    "no_materialized_view",
    f"you declared a materialized view {freshness} on {engine}, which has no materialized "
    f"view of its own and nothing to build one from", {"freshness": freshness, "engine": engine})


_refuse_freshness = lambda freshness, _engine, _capability: refused(
    "no_such_freshness",
    f"you declared a materialized view {freshness!r}, which is not one of "
    f"{list(_DECLARED_FRESHNESSES)}", {"accepted": list(_DECLARED_FRESHNESSES), "arrived": freshness})


_MECHANISM_ANSWER = {"native": _mechanism_operations, "built": _mechanism_operations, "nothing": _refuse_mechanism_engine}


_on_freshness = lambda freshness, engine, capability: _read_or(
    _MECHANISM_ANSWER,
    _OFFERS[(capability["native"], bool(capability["built_from"].strip()))],
    lambda: _refuse_mechanism_engine)(freshness, engine, capability)


_ON_FRESHNESS = {True: _on_freshness, False: _refuse_freshness}


def mechanism_for(freshness, engine, capability):
    """Pick the mechanism that gives a materialized view the freshness asked for (declaration
    mechanism_for)."""
    return _ON_FRESHNESS[freshness in _DECLARED_FRESHNESSES](freshness, engine, capability)
