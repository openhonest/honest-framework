"""The query half: a caller's writing read into one engine-free declaration, and compiled.

Four grammar readers (grammar_of, methods_of, asked_from_written, declaration_from_asked), the narrowing
reader (condition_from_narrowing), the compiler (compile_statement), the answer shapers (answer_from_rows,
answer_from_receipt), the join (join_between) and the two model checks (refuse_undeclared_columns,
refuse_some_columns_as_an_object). Ported from declaro-persistum, adapted to honest-persist's bare-union
Fault and its NoMatch records: a word no table holds is a NoMatch, a malformed shape is a Fault.
"""

from honest_persist._util import _pick, _read_or
from honest_persist.types import (
    GRAMMARS,
    OPERATORS,
    WANTED,
    WRITINGS,
    is_fault,
    is_no_match,
    no_match,
    refused,
)

NOTHING = None


# Whether a step handed back a refusal rather than what it was asked for: a Fault or a NoMatch.
_is_refusal = lambda built: is_fault(built) or is_no_match(built)


# --- grammar_of: which spelling, read off the shape (declaration grammar_of) --------------------------
_MARKS = {"django": ".objects.", "sqlalchemy": ".query.", "prisma": "find_many("}


_first_mark = lambda marked, _written: marked[0]


# Nothing marked it, so it is this library's own spelling or it is a miss.
_no_mark = lambda _marked, written: _PSEUDO_OR_MISS["." in written and "(" in written](written)


_PSEUDO_OR_MISS = {
    True: lambda _written: "pseudo_sql",
    False: lambda written: no_match("grammars", [], sorted(GRAMMARS), "no_key_to_look_up", written),
}

_ANY_MARK = {True: _first_mark, False: _no_mark}


def grammar_of(written):
    """Which way of writing this is, read off the punctuation and shape (declaration grammar_of). A
    question marking no spelling answers a NoMatch, reason no_key_to_look_up, because nothing in the text
    named one; a caller holding their own text and the four spellings can write it again."""
    marked = list(filter(lambda spelling: _read_or(_MARKS, spelling, lambda: "") in written, _MARKS))
    return _ANY_MARK[marked != []](marked, written)


# --- methods_of: the method names one spelling uses (declaration methods_of) --------------------------
_METHOD_NAMES = {
    "pseudo_sql": {},
    "prisma": {},
    "django": {"where": "filter", "select": "values"},
    "sqlalchemy": {"where": "filter_by", "select": "with_only"},
}


def methods_of(grammar):
    """The method names one way of writing uses, one row per way (declaration methods_of)."""
    return _read_or(_METHOD_NAMES, grammar, lambda: {})


# --- condition_from_narrowing: a caller's narrowing into this library's condition ---------------------
_COMPANION = "ignore_case"
_ANY_OF = "or"
_NONE_OF = "not"


# `{"name": "bob"}`. A bare value means eq, so this is where it says so.
_a_bare_value = lambda written: {"operator": "eq", "value": written, "ignore_case": False}


_IGNORE_CASE = {
    True: lambda written: bool(written[_COMPANION]),
    False: lambda _written: False,
}


def _the_comparison(written, named):
    """`{"gt": 18}`, `{"between": [18, 30]}`, or `{"like": "bo%", "ignore_case": True}`."""
    operator = named[0]
    return {
        "operator": operator,
        "value": written[operator],
        "ignore_case": _IGNORE_CASE[_COMPANION in written](written),
    }


# A key inside a comparison that is not one of the fifteen: a NoMatch naming operators.
_an_operator_nobody_declared = lambda written, named: no_match(
    "operators", list(filter(lambda word: word not in OPERATORS, named)), sorted(OPERATORS),
    "no_row_for_the_key", repr(written))


# A comparison holds one operator and one value, so a second has nowhere to go and a zeroth leaves the
# value with nothing to compare by: a Fault, because nothing was looked up.
_not_exactly_one_operator = lambda _written, named: refused(
    "comparison_operator_count",
    f"a comparison names one operator and one value, and this one names {len(named)}: {named}",
    {"named": named},
)


_ONE_DECLARED_OPERATOR = {
    (True, True): _the_comparison,
    (True, False): _an_operator_nobody_declared,
    (False, True): _not_exactly_one_operator,
    (False, False): _an_operator_nobody_declared,
}


def _a_named_operator(written):
    """A comparison written as a dict, which is the caller naming an operator."""
    named = list(filter(lambda key: key != _COMPANION, written))
    return _ONE_DECLARED_OPERATOR[(len(named) == 1, set(named) <= OPERATORS)](written, named)


_LIST_ANSWER = {
    False: lambda built, _refusals: built,
    True: lambda _built, refusals: refusals[0],
}


def _each_one_of(written):
    """Every condition hung under `or` or under `not`, or the first refusal."""
    built = [_built_from("condition", one) for one in written]
    refusals = list(filter(_is_refusal, built))
    return _LIST_ANSWER[refusals != []](built, refusals)


_MANY_CONDITIONS = {
    list: lambda written: written,
    dict: lambda written: [written],
}

_COMBINED = {
    True: lambda written: _each_one_of(_MANY_CONDITIONS[type(written)](written)),
    False: lambda written: _nothing_to_do_with("condition", written),
}


_conditions_under = lambda written: _COMBINED[type(written) in _MANY_CONDITIONS](written)


_NOT_A_COLUMN = {_ANY_OF: _conditions_under, _NONE_OF: _conditions_under}


_assembled = lambda built, _refusals: {
    "each": {key: one for key, one in filter(lambda ko: ko[0] not in _NOT_A_COLUMN, built.items())},
    "any_of": built[_ANY_OF],
    "none_of": built[_NONE_OF],
}


_the_first_refusal = lambda _built, refusals: refusals[0]


_CONDITION_ANSWER = {False: _assembled, True: _the_first_refusal}

_A_COMBINING_KEY = {
    True: lambda key, value: _read_or(_NOT_A_COLUMN, key, lambda: _conditions_under)(value),
    False: lambda _key, value: _a_comparison_for(value),
}


def _each_key_of(written):
    """A narrowing written as data, starting with `or` and `not` present and empty so _assembled reads
    both by name."""
    built = {_ANY_OF: [], _NONE_OF: []}
    built.update({key: _A_COMBINING_KEY[key in _NOT_A_COLUMN](key, value) for key, value in written.items()})
    refusals = list(filter(_is_refusal, built.values()))
    return _CONDITION_ANSWER[refusals != []](built, refusals)


_a_comparison_for = lambda written: _built_from("comparison", written)


_narrowed_by_nothing = lambda _written: {"each": {}, "any_of": [], "none_of": []}


_SHAPES = {
    "comparison": {
        dict: _a_named_operator,
        str: _a_bare_value,
        int: _a_bare_value,
        float: _a_bare_value,
        bool: _a_bare_value,
        type(NOTHING): _a_bare_value,
    },
    "condition": {
        dict: _each_key_of,
        type(NOTHING): _narrowed_by_nothing,
    },
}

_WHAT_IT_IS = {
    "comparison": "a comparison is a value, or a dict naming one of the fifteen operators",
    "condition": "a condition is data, written as a dict, or left out entirely",
}


_nothing_to_do_with = lambda what, written: refused(
    "narrowing_shape",
    f"{_read_or(_WHAT_IT_IS, what, lambda: 'a narrowing')}, and this one arrived as {type(written).__name__}: {written!r}",
    {"shape": type(written).__name__},
)


_A_SHAPE_WITH_A_ROW = {
    True: lambda what, written: _read_or(_SHAPES, what, lambda: {})[type(written)](written),
    False: lambda what, written: _nothing_to_do_with(what, written),
}


_built_from = lambda what, written: _A_SHAPE_WITH_A_ROW[type(written) in _read_or(_SHAPES, what, lambda: {})](what, written)


def condition_from_narrowing(narrowing):
    """Turn what a caller wrote into the condition this library holds (declaration
    condition_from_narrowing): a bare value means eq, `or` and `not` become `any_of` and `none_of`. A
    word inside a comparison the operators table holds no row for answers a NoMatch naming operators; a
    comparison naming the wrong number of operators is a Fault, because nothing was looked up."""
    return _built_from("condition", narrowing)


# --- refuse_undeclared_columns, refuse_some_columns_as_an_object, travels_together --------------------
# Every column a condition names, however deep it is nested.
_named_in = lambda condition: list(condition["each"]) + [
    name for inner in condition["any_of"] + condition["none_of"] for name in _named_in(inner)
]


_WHERE_COLUMNS_ARE_NAMED = {
    "columns": lambda declaration: list(declaration["columns"]),
    "condition": lambda declaration: _named_in(declaration["condition"]),
    "order": lambda declaration: list(declaration["order"]),
    "grouping": lambda declaration: list(declaration["grouping"]),
    "having": lambda declaration: _named_in(declaration["having"]),
}


_nothing_undeclared = lambda _model, _declaration, _unknown: NOTHING


_refuse_undeclared = lambda model, _declaration, unknown: refused(
    "undeclared_column",
    f"{model['name']} declares no column {sorted(unknown)}; its columns are "
    f"{[column['name'] for column in model['columns']]}",
    {"model": model["name"], "unknown": sorted(unknown),
     "declares": [column["name"] for column in model["columns"]]},
)


_UNDECLARED_ANSWER = {False: _nothing_undeclared, True: _refuse_undeclared}


def refuse_undeclared_columns(model, declaration):
    """Refuse a column no model declares, naming the model and its columns (declaration
    refuse_undeclared_columns). Checks the five places a declaration names a column."""
    declares = {column["name"] for column in model["columns"]}
    named = [
        name
        for place in _WHERE_COLUMNS_ARE_NAMED.values()
        for name in place(declaration)
    ]
    unknown = set(filter(lambda name: name not in declares, named))
    return _UNDECLARED_ANSWER[unknown != set()](model, declaration, unknown)


_nothing_to_refuse = lambda _declaration: NOTHING


def _a_part_cannot_be_the_whole(declaration):
    named = declaration["columns"]
    return refused(
        "columns_as_object",
        f"you asked {declaration['model']} for {len(named)} of its columns, {sorted(named)}, and asked "
        f"for the rows back as your own model. A row carrying {len(named)} fields is not a "
        f"{declaration['model']}. Ask for the whole row and keep your model, or keep the columns and "
        f"take the rows back as dictionaries.",
        {"model": declaration["model"], "columns": sorted(named)},
    )


_COLUMNS_AS_OBJECT = {True: _a_part_cannot_be_the_whole, False: _nothing_to_refuse}


def refuse_some_columns_as_an_object(declaration):
    """Refuse a question that asks for some columns and for your own model at once, naming both words
    (declaration refuse_some_columns_as_an_object)."""
    asked_for_part = bool(declaration["columns"])
    return _COLUMNS_AS_OBJECT[asked_for_part and declaration["shaping"] == "objects"](declaration)


def travels_together(declaration):
    """Answer whether these writes have to land together (declaration travels_together): one row is a
    deposit and a ticket, several rows handed to one call are a transaction."""
    return declaration["wanted"] in WRITINGS and len(declaration["rows"] or ()) > 1


# --- refuse_a_read: the deposit door stays write-only (declaration refuse_a_read, spec 8.6) -----------
_a_write_is_deferrable = lambda _declaration: NOTHING


def _a_read_cannot_be_deposited(declaration):
    word = declaration["wanted"]
    return refused(
        "read_cannot_be_deposited",
        f"`{word}` is a reading, and the asynchronous deposit door takes only writings "
        f"{sorted(WRITINGS)}; the write queue holds a write as data to defer and drain, and a read "
        f"answers now with nothing to hold, so send it to query_ask instead",
        {"wanted": word, "writings": sorted(WRITINGS)},
    )


_WRITE_OR_READ = {True: _a_write_is_deferrable, False: _a_read_cannot_be_deposited}


def refuse_a_read(declaration):
    """Refuse a declaration whose asking word is a reading rather than a writing, so the asynchronous
    deposit door stays write-only (declaration refuse_a_read, spec 8.6). A writing word passes as NOTHING;
    a reading word is the refused retry class, because a read fails identically however often it runs and
    the caller must change it, not retry it."""
    return _WRITE_OR_READ[declaration["wanted"] in WRITINGS](declaration)


# --- the answer shapers (declaration answer_from_rows, answer_from_receipt) ---------------------------
# all / distinct / page / the groups: the rows as they came, dictionaries.
_rows_of_the_model = lambda _model, rows, _declaration: rows


_one_refusal = lambda rows: refused("not_exactly_one", f"one asked for exactly one row and {len(rows)} matched", {"matched": len(rows)})


_ONE_OF = {0: lambda _rows: NOTHING, 1: lambda rows: rows[0]}


_read_count = lambda count: _pick(count in (0, 1), lambda: _read_or(_ONE_OF, count, lambda: _one_refusal), lambda: _one_refusal)


# one: exactly one row, an absence, or a refusal naming how many matched.
_exactly_one = lambda _model, rows, _declaration: _read_count(len(rows))(rows)


# first: the first row, or NOTHING.
_the_first = lambda _model, rows, _declaration: next(iter(rows), NOTHING)


# exists: true or false, read off the single EXISTS column the engine answered.
_true_or_false = lambda _model, rows, _declaration: bool(next(iter(next(iter(rows), {}).values()), False))


# count / sum / average / smallest / largest / count_distinct: the one number.
_a_number = lambda _model, rows, _declaration: next(iter([value for row in rows for value in row.values()]), 0)


_not_a_read = lambda model, _rows, declaration: refused(
    "write_has_no_rows",
    f"`{declaration['wanted']}` writes to {model['table']}, and a write has no rows to shape",
    {"wanted": declaration["wanted"]},
)


_BY_READING_WORD = {
    "all": _rows_of_the_model, "distinct": _rows_of_the_model, "page": _rows_of_the_model,
    "one": _exactly_one, "first": _the_first, "exists": _true_or_false,
    "count": _a_number, "sum": _a_number, "average": _a_number, "smallest": _a_number,
    "largest": _a_number, "count_distinct": _a_number,
}

_WRITE_SHAPES = {word: _not_a_read for word in WRITINGS}
_ANSWER_SHAPE = {**_BY_READING_WORD, **_WRITE_SHAPES}


def answer_from_rows(model, rows, declaration):
    """Shape driver rows the way the caller asked (declaration answer_from_rows): your own objects, plain
    rows, a number, true or false, or NOTHING."""
    return _ANSWER_SHAPE[declaration["wanted"]](model, rows, declaration)


_how_many_rows_it_touched = lambda receipt: receipt["touched"]


_the_failure_it_carries = lambda receipt: receipt["failure"]


_FROM_RECEIPT = {True: _how_many_rows_it_touched, False: _the_failure_it_carries}


def answer_from_receipt(receipt):
    """Turn what the drainer did into the count a caller reads (declaration answer_from_receipt); a
    not-ok receipt surfaces the Fault it carries."""
    return _FROM_RECEIPT[receipt["ok"]](receipt)


# --- join_between: the join the foreign key already declared (declaration join_between) ---------------
def _keys_declared_by(pointing, pointed_at):
    over_there = {column["name"] for column in pointed_at["columns"]}
    return sorted(
        (column["name"], column["references"]["column"])
        for column in filter(
            lambda c: c["references"] is not None
            and c["references"]["table"] == pointed_at["table"]
            and c["references"]["column"] in over_there,
            pointing["columns"],
        )
    )


_keys_between = lambda near, far: _keys_declared_by(near, far) + [
    (on_near, on_far) for on_far, on_near in _keys_declared_by(far, near)
]


def _the_key_declared(keys, _near, far, condition):
    by_column, to_column = keys[0]
    return {"model": far["table"], "by_column": by_column, "to_column": to_column, "condition": condition}


_no_key_joins_them = lambda _keys, near, far, _condition: refused(
    "no_join",
    f"no key joins {near['table']} and {far['table']}; neither model declares a column that "
    f"references the other",
    {"near": near["table"], "far": far["table"]},
)


_JOIN_ANSWER = {True: _the_key_declared, False: _no_key_joins_them}


def join_between(near, far, condition):
    """Work out the join from the foreign key the model already declared (declaration join_between)."""
    keys = _keys_between(near, far)
    return _JOIN_ANSWER[keys != []](keys, near, far, condition)


# --- asked_from_written and declaration_from_asked ---------------------------------------------------
from honest_persist._query_read import asked_from_written, declaration_from_asked  # noqa: E402,F401
from honest_persist._compile import compile_statement  # noqa: E402,F401
