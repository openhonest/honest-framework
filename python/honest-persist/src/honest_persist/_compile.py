"""compile_statement: a declaration and an engine in, a statement and its values out.

The last step, and the only one that knows which engine it is talking to. Ported from declaro-persistum,
adapted to honest-persist's bare-union Fault and its NoMatch records: an asking word the renderers table
holds no row for is a NoMatch naming asking_words; a declaration short of what its word needs is a Fault.
Values are never pasted into the text; they come back in `parameters` for the driver to bind.
"""

from honest_persist._util import _pick, _read_or
from honest_persist.engines import how_to_compare
from honest_persist.types import WANTED, no_match, refused

_THREE_ENGINES = ("postgresql", "sqlite", "turso")
_A_DECLARATION_HAS = frozenset({
    "model", "wanted", "columns", "condition", "order", "grouping", "having", "paging", "rows",
    "shaping", "across",
})

_ENGINE = {
    "postgresql": {"placeholder": lambda position: f"${position}",
                   "quote": lambda name: '"' + name.replace('"', '""') + '"'},
    "sqlite": {"placeholder": lambda _position: "?",
               "quote": lambda name: '"' + name.replace('"', '""') + '"'},
    "turso": {"placeholder": lambda _position: "?",
              "quote": lambda name: '"' + name.replace('"', '""') + '"'},
}


# One engine's placeholder and quote functions. Reached only after compile_statement matched the engine
# against the three it ships, so the read is a guaranteed hit; it goes through _read_or so the subscript
# is on a local, never on a module dispatch dict by a bare key (P16).
_engine_row = lambda engine: _read_or(_ENGINE, engine, lambda: _ENGINE["sqlite"])


_said = lambda word, clause: {True: "", False: f"{word} {clause}"}[clause == ""]


_bracketed = lambda clause: {True: "", False: f"({clause})"}[clause == ""]


_sentence = lambda *pieces: " ".join(filter(None, pieces))


_HOW_MANY_VALUES = {
    "one": lambda column, symbol, asked, bind, _wraps: f"{column} {symbol} {bind(asked['value'])}",
    "list": lambda column, symbol, asked, bind, _wraps: (
        f"{column} {symbol} (" + ", ".join(bind(one) for one in asked["value"]) + ")"
    ),
    "range": lambda column, symbol, asked, bind, _wraps: (
        f"{column} {symbol} " + bind(asked["value"][0]) + " AND " + bind(asked["value"][1])
    ),
    "pattern": lambda column, symbol, asked, bind, wraps: (
        f"{column} {symbol} " + " || ".join(filter(None, (
            _pick(bool(wraps.split("{}")[0]), lambda: f"'{wraps.split('{}')[0]}'", lambda: ""),
            bind(asked["value"]),
            _pick(bool(wraps.split("{}")[1]), lambda: f"'{wraps.split('{}')[1]}'", lambda: ""),
        )))
    ),
    "none": lambda column, symbol, _asked, _bind, _wraps: f"{column} {symbol}",
}

_WHEN_CASE_DOES_NOT_MATTER = {
    True: lambda _symbol, instead, _plain: (instead, lambda sql: sql),
    False: lambda symbol, _instead, fold: (symbol, fold),
}

_CASE = {False: lambda sql: sql, True: lambda sql: f"LOWER({sql})"}


def _narrowing(condition, compare):
    def _joined(word, parts):
        kept = list(filter(None, parts))
        return {True: "", False: "(" + f" {word} ".join(kept) + ")"}[kept == []]

    each = [compare(column, asked) for column, asked in condition["each"].items()]
    any_of = [_joined("OR", [_bracketed(_narrowing(one, compare)) for one in condition["any_of"]])]
    none_of = [_said("NOT", _joined("AND", [_bracketed(_narrowing(one, compare)) for one in condition["none_of"]]))]
    return " AND ".join(filter(None, each + any_of + none_of))


_asks_for_nothing = lambda condition: (
    condition["each"] == {} and condition["any_of"] == [] and condition["none_of"] == []
)


_across = lambda declaration, quote: " ".join(
    f"INNER JOIN {quote(join['model'])} ON "
    f"{quote(declaration['model'])}.{quote(join['by_column'])} = "
    f"{quote(join['model'])}.{quote(join['to_column'])}"
    for join in declaration["across"] or ()
)


def _order(declaration, quote):
    direction = {"ascending": "ASC", "descending": "DESC"}
    return _said("ORDER BY", ", ".join(
        f"{quote(column)} {direction[way]}" for column, way in declaration["order"].items()
    ))


_grouping = lambda declaration, quote: _said(
    "GROUP BY", ", ".join(quote(column) for column in declaration["grouping"])
)


_columns = lambda declaration, quote: ", ".join(
    quote(column) for column in declaration["columns"]
) or "*"


_measured = lambda declaration, quote: ", ".join(
    quote(column) for column in declaration["columns"][:1]
) or "*"


_reading = lambda declaration, quote, _bind, compare, select_list, tail: _sentence(
    f"SELECT {select_list}",
    f"FROM {quote(declaration['model'])}",
    _across(declaration, quote),
    _said("WHERE", _narrowing(declaration["condition"], compare)),
    _grouping(declaration, quote),
    _said("HAVING", _narrowing(declaration["having"], compare)),
    _order(declaration, quote),
    tail,
)


_MEASURE = {
    "count": "COUNT({column})", "sum": "SUM({column})", "average": "AVG({column})",
    "smallest": "MIN({column})", "largest": "MAX({column})", "count_distinct": "COUNT(DISTINCT {column})",
}


def _measuring(word):
    def built(declaration, quote, bind, compare):
        groups = [quote(column) for column in declaration["grouping"]]
        measured = _read_or(_MEASURE, word, lambda: "{column}").format(column=_measured(declaration, quote))
        return _reading(declaration, quote, bind, compare, ", ".join([*groups, measured]), "")

    return built


_all = lambda declaration, quote, bind, compare: _reading(
    declaration, quote, bind, compare, _columns(declaration, quote), "",
)


_one = lambda declaration, quote, bind, compare: _reading(
    declaration, quote, bind, compare, _columns(declaration, quote), "LIMIT 2",
)


_first = lambda declaration, quote, bind, compare: _reading(
    declaration, quote, bind, compare, _columns(declaration, quote), "LIMIT 1",
)


def _page(declaration, quote, bind, compare):
    paging = declaration["paging"] or {}
    size = bind(paging["size"])
    skipped = bind(paging["size"] * (paging["number"] - 1))
    return _reading(declaration, quote, bind, compare, _columns(declaration, quote), f"LIMIT {size} OFFSET {skipped}")


_distinct = lambda declaration, quote, bind, compare: _reading(
    declaration, quote, bind, compare, f"DISTINCT {_columns(declaration, quote)}", "",
)


_exists = lambda declaration, quote, _bind, compare: "SELECT EXISTS(" + _sentence(
    "SELECT 1", f"FROM {quote(declaration['model'])}", _across(declaration, quote),
    _said("WHERE", _narrowing(declaration["condition"], compare)), "LIMIT 1",
) + ")"


def _add(declaration, quote, bind, _compare):
    rows = declaration["rows"] or []
    columns = list(rows[0])
    written = ", ".join("(" + ", ".join(bind(row[column]) for column in columns) + ")" for row in rows)
    return (f"INSERT INTO {quote(declaration['model'])} (" + ", ".join(quote(column) for column in columns)
            + ") " + f"VALUES {written}")


def _change(declaration, quote, bind, compare):
    (row,) = declaration["rows"] or [{}]
    setting = ", ".join(f"{quote(column)} = {bind(value)}" for column, value in row.items())
    return _sentence(f"UPDATE {quote(declaration['model'])}", f"SET {setting}",
                     _said("WHERE", _narrowing(declaration["condition"], compare)))


_remove = lambda declaration, quote, _bind, compare: _sentence(
    f"DELETE FROM {quote(declaration['model'])}",
    _said("WHERE", _narrowing(declaration["condition"], compare)),
)


_SHAPE = {
    "all": _all, "one": _one, "first": _first, "page": _page, "distinct": _distinct, "exists": _exists,
    "count": _measuring("count"), "sum": _measuring("sum"), "average": _measuring("average"),
    "smallest": _measuring("smallest"), "largest": _measuring("largest"),
    "count_distinct": _measuring("count_distinct"),
    "add": _add, "change": _change, "change_all": _change, "remove": _remove, "remove_all": _remove,
    "replace": lambda _declaration, _quote, _bind, _compare: "",
}

_MET = {
    "an order to be first in": lambda declaration: declaration["order"] != {},
    "a page to fetch": lambda declaration: declaration["paging"] is not None,
    "a page number counted from one": lambda declaration: (declaration["paging"] or {"number": 1})["number"] >= 1,
    "a column to measure": lambda declaration: declaration["columns"] != [],
    "the rows it is declaring": lambda declaration: declaration["rows"] not in (None, []),
    "exactly one row to change": lambda declaration: len(declaration["rows"] or []) == 1,
    "a narrowing saying which rows": lambda declaration: not _asks_for_nothing(declaration["condition"]),
    "a key to conflict on": lambda _declaration: False,
}

_INSTEAD = {
    "an order to be first in": "State the order.",
    "a page to fetch": "State the page: how big it is and which one you want.",
    "a page number counted from one": "Number the pages from one.",
    "a column to measure": "Name the one column to measure.",
    "the rows it is declaring": "Hand over the rows you are declaring exist.",
    "exactly one row to change": "Hand over one row of new values.",
    "a narrowing saying which rows": "Narrow it.",
    "a key to conflict on": "Ask for add, or for change with a narrowing. An upsert has to name a key.",
}

_NEEDS = {
    "all": (), "one": (), "first": ("an order to be first in",),
    "page": ("a page to fetch", "a page number counted from one"),
    "distinct": ("a column to measure",), "exists": (), "count": (),
    "sum": ("a column to measure",), "average": ("a column to measure",),
    "smallest": ("a column to measure",), "largest": ("a column to measure",),
    "count_distinct": ("a column to measure",),
    "add": ("the rows it is declaring",),
    "change": ("exactly one row to change", "a narrowing saying which rows"),
    "change_all": ("exactly one row to change", "a narrowing saying which rows"),
    "remove": ("a narrowing saying which rows",), "remove_all": ("a narrowing saying which rows",),
    "replace": ("a key to conflict on",),
}


_not_a_declaration = lambda declaration, _engine: refused(
    "not_a_declaration",
    f"the renderer was handed a {type(declaration).__name__} and it compiles a declaration",
    {"arrived": type(declaration).__name__},
)


_no_such_engine = lambda _declaration, engine: refused(
    "no_such_engine",
    f"no engine here is called {engine!r}; this package compiles for {_THREE_ENGINES}",
    {"accepted": list(_THREE_ENGINES), "arrived": engine},
)


_no_such_word = lambda declaration, _engine: no_match(
    "asking_words", [declaration["wanted"]], sorted(WANTED), "no_row_for_the_key",
    f"wanted {declaration['wanted']!r}",
)


_unmet = lambda declaration: list(filter(
    lambda need: not _read_or(_MET, need, lambda: lambda _d: False)(declaration),
    _NEEDS[declaration["wanted"]],
))


def _short_of_what_it_needs(declaration, _engine):
    missing = _unmet(declaration)
    return refused("declaration_incomplete",
                   f"a {declaration['wanted']} needs " + ", and ".join(missing)
                   + ". " + _INSTEAD[missing[0]], {"missing": missing})


def _compiled(declaration, engine):
    # A way to put each value beside the statement and get back its placeholder; the kept dict lives only
    # for this compile.
    def _binder(engine):
        kept = {}
        spell = _engine_row(engine)["placeholder"]

        def bind(value):
            kept[f"p{len(kept) + 1}"] = value
            return spell(len(kept))

        return bind, kept

    def _comparer(engine, quote, bind):
        def compared(column, asked):
            how = how_to_compare(asked["operator"], engine)
            symbol, fold = _WHEN_CASE_DOES_NOT_MATTER[asked["ignore_case"] and bool(how["ignoring_case"])](
                how["symbol"], how["ignoring_case"], _CASE[asked["ignore_case"]],
            )
            return _HOW_MANY_VALUES[how["shape"]](
                fold(quote(column)), symbol, asked, lambda value: fold(bind(value)), how["wraps"],
            )

        return compared

    quote = _engine_row(engine)["quote"]
    bind, parameters = _binder(engine)
    return {"text": _SHAPE[declaration["wanted"]](declaration, quote, bind, _comparer(engine, quote, bind)),
            "parameters": parameters}


_WHEN_IT_HAS_WHAT_IT_NEEDS = {True: _compiled, False: _short_of_what_it_needs}


_with_a_declared_word = lambda declaration, engine: _WHEN_IT_HAS_WHAT_IT_NEEDS[
    _unmet(declaration) == []
](declaration, engine)


_WHEN_THE_WORD_IS_DECLARED = {True: _with_a_declared_word, False: _no_such_word}


_with_a_declared_engine = lambda declaration, engine: _WHEN_THE_WORD_IS_DECLARED[
    declaration["wanted"] in _SHAPE
](declaration, engine)


_WHEN_THE_ENGINE_IS_DECLARED = {True: _with_a_declared_engine, False: _no_such_engine}


_with_a_declaration = lambda declaration, engine: _WHEN_THE_ENGINE_IS_DECLARED[
    engine in _THREE_ENGINES
](declaration, engine)


_WHEN_IT_IS_A_DECLARATION = {True: _with_a_declaration, False: _not_a_declaration}


_is_a_declaration = lambda declaration: isinstance(declaration, dict) and frozenset(declaration) >= _A_DECLARATION_HAS


def compile_statement(declaration, engine):
    """Compile a declaration into one engine's statement, values kept beside it (declaration
    compile_statement). An asking word the renderers table holds no row for answers a NoMatch naming
    asking_words; a declaration short of what its word needs is a Fault, because the word was found."""
    return _WHEN_IT_IS_A_DECLARATION[_is_a_declaration(declaration)](declaration, engine)
