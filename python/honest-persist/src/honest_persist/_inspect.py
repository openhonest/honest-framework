"""schema_inspect: what a database holds right now, asked for rather than assumed.

Ported from declaro-persistum, adapted to honest-persist's bare-union Fault. It asks the engine the six
questions how_to_inspect hands it, all answered under the same names on every engine, and builds the live
schema out of the answers. A question the engine refuses comes back as a Fault, because a migration
worked out from a half-read schema drops whatever it could not see.
"""

import re

from honest_persist._util import _read_or
from honest_persist.types import is_fault, refused

NOTHING = None
_NARROWS_BY_NOTHING = {"each": {}, "any_of": [], "none_of": []}
_IN_THE_DDL = "in_the_ddl"

_A_NAMED_RULE = re.compile(
    r'CONSTRAINT\s+["`\[]?(?P<name>\w+)["`\]]?\s+(?P<kind>CHECK|PRIMARY\s+KEY|UNIQUE)', re.IGNORECASE)
_WHAT_SQL_CALLS_IT = {"CHECK": "check", "PRIMARY KEY": "primary_key", "UNIQUE": "unique"}
_WHAT_POSTGRESQL_CALLS_IT = {"c": "check", "p": "primary_key", "u": "unique", "f": "check"}


def _refused_inspect(asked, said):
    return refused("inspection_refused",
                   f"a database could not be asked what {asked} it holds: {said['message']}", {})


async def _ask(query_run_statement, connection, engine, question, about):
    asked = {"text": question["text"], "parameters": dict.fromkeys(question["parameters"], about)}
    return await query_run_statement(connection, engine, asked)


def _plainly(spelled):
    return spelled.split("(")[0].strip().lower()


def _no_word_for_it(spelled, table, _types):
    return refused("no_word_for_type",
                   f"the column in {table!r} is a {spelled!r}, and this package has no word for it", {})


def _the_word(spelled, _table, types):
    return types[_plainly(spelled)]


_TYPE_KNOWN = {True: _the_word, False: _no_word_for_it}


def _a_column(row, table, types):
    spelled = str(row["declared_type"])
    held = _TYPE_KNOWN[_plainly(spelled) in types](spelled, table, types)
    return _COLUMN_READ[is_fault(held)](row, held)


_COLUMN_READ = {
    True: lambda _row, held: held,
    False: lambda row, held: {"name": str(row["name"]), "declared_type": held,
                              "renamed_from": None, "references": None},
}


def _an_index(row):
    return {"name": str(row["name"]), "columns": [], "unique": bool(row["is_unique"])}


def _a_rule(name, kind, columns):
    return {"name": name, "kind": kind, "columns": columns, "rule": _NARROWS_BY_NOTHING, "value": None}


def _the_rules_the_columns_carry(columns):
    return [
        _a_rule(f"{under}_{row['name']}", under, [str(row["name"])])
        for row in columns
        for under, held in filter(lambda uh: bool(row[uh[1]]),
                                  (("not_null", "must_hold_something"), ("primary_key", "is_key")))
    ]


def _the_rules_in_the_ddl(spelled_out):
    return [
        _a_rule(found.group("name"), _WHAT_SQL_CALLS_IT[" ".join(found.group("kind").upper().split())], [])
        for found in _A_NAMED_RULE.finditer(spelled_out)
    ]


def _the_rules_a_catalogue_carries(row):
    said = str(row["kind"])
    return [_a_rule(str(row["name"]), _read_or(_WHAT_POSTGRESQL_CALLS_IT, said, lambda: ""), []) for _ in range(int(said in _WHAT_POSTGRESQL_CALLS_IT))]


_WHERE_THE_RULES_ARE = {
    True: lambda row: _the_rules_in_the_ddl(str(row["spelled_out"] or "")),
    False: _the_rules_a_catalogue_carries,
}


def _the_rules_in(constraints, columns):
    return [
        *_the_rules_the_columns_carry(columns),
        *[rule for row in constraints for rule in _WHERE_THE_RULES_ARE[str(row["kind"]) == _IN_THE_DDL](row)],
    ]


async def _one_table(query_run_statement, connection, engine, inspecting, name):
    asked = {
        about: await _ask(query_run_statement, connection, engine, inspecting[about], name)
        for about in ("columns", "indexes", "constraints")
    }
    refused_qs = [_refused_inspect(about, answer) for about, answer in filter(lambda aa: is_fault(aa[1]), asked.items())]
    return _FIRST_REFUSAL_OR[refused_qs != []](refused_qs, asked, name, inspecting["types"])


def _a_table_out_of_the_answers(_refused, asked, name, types):
    columns = asked["columns"]
    read = [_a_column(row, name, types) for row in columns]
    unreadable = list(filter(is_fault, read))
    return _EVERY_COLUMN_READ[unreadable != []](asked, name, read, unreadable)


_EVERY_COLUMN_READ = {
    True: lambda _asked, _name, _read, unreadable: unreadable[0],
    False: lambda asked, name, read, _unreadable: {
        "name": name, "columns": read,
        "indexes": [_an_index(row) for row in asked["indexes"]],
        "constraints": _the_rules_in(asked["constraints"], asked["columns"]),
    },
}

_FIRST_REFUSAL_OR = {
    True: lambda refused_qs, _asked, _name, _types: refused_qs[0],
    False: _a_table_out_of_the_answers,
}


def _a_view(row):
    return {"name": str(row["name"]), "declaration": NOTHING, "freshness": NOTHING,
            "cadence": NOTHING, "attempts_allowed": NOTHING}


async def schema_inspect(connection, engine, inspecting):
    """Ask a database the six questions and build what it holds out of the answers (declaration
    schema_inspect). A database with nothing in it comes back as a schema with nothing in it; a question
    the engine refused comes back as a Fault."""
    from honest_persist.io import query_run_statement

    tables = await _ask(query_run_statement, connection, engine, inspecting["tables"], "")
    views = await _ask(query_run_statement, connection, engine, inspecting["views"], "")
    refused_qs = [
        _refused_inspect(about, answer)
        for about, answer in filter(lambda aa: is_fault(aa[1]), (("tables", tables), ("views", views)))
    ]
    held = [
        await _one_table(query_run_statement, connection, engine, inspecting, str(row["name"]))
        for row in _TABLES_OR_NONE[is_fault(tables)](tables)
    ]
    every_refusal = [*refused_qs, *filter(is_fault, held)]
    return _SCHEMA_OR_FIRST_REFUSAL[every_refusal != []](every_refusal, held, views)


_TABLES_OR_NONE = {True: lambda _tables: [], False: lambda tables: tables}

_SCHEMA_OR_FIRST_REFUSAL = {
    True: lambda every_refusal, _held, _views: every_refusal[0],
    False: lambda _every_refusal, held, views: {"tables": held, "views": [_a_view(row) for row in views]},
}
