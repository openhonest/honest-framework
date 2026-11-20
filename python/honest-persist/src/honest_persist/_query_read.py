"""asked_from_written and declaration_from_asked: the four spellings read into one declaration.

declaration_from_asked is the shared builder and the one place a missing part is told no (ported from
declaro-persistum, adapted so an asking word no row holds answers a NoMatch naming asking_words).
asked_from_written lifts the parts out of one spelling; this is a working reduced parser (the four
grammars are read into a model, an asking word, and the parts beside it), enough to build a declaration
and to answer a NoMatch on a method name no spelling gives a part.
"""

import ast

from honest_persist._util import _pick, _read_or
from honest_persist.query import condition_from_narrowing
from honest_persist.types import WANTED, is_fault, is_no_match, no_match, refused

NOTHING = None


def _is_refusal(piece):
    return is_fault(piece) or is_no_match(piece)


# --- declaration_from_asked (declaration declaration_from_asked) -------------------------------------
_WHICH_FIELD_EACH_PART_FILLS = {
    "select": "columns", "where": "condition", "ordered_by": "order", "grouped_by": "grouping",
    "having": "having", "paging": "paging", "across": "across", "rows": "rows", "model": "model",
    "wanted": "wanted", "shaping": "shaping",
}

_WHAT_EMPTY_MEANS = {
    "columns": lambda: [], "grouping": lambda: [],
    "condition": lambda: {"each": {}, "any_of": [], "none_of": []},
    "having": lambda: {"each": {}, "any_of": [], "none_of": []},
    "order": lambda: {}, "paging": lambda: NOTHING, "rows": lambda: NOTHING,
    "across": lambda: NOTHING, "shaping": lambda: "dictionaries",
}

_CANNOT_DO_WITHOUT = ("model", "wanted")
_EVERY_FIELD = ("model", "wanted", "columns", "condition", "order", "grouping", "having", "paging",
                "rows", "shaping", "across")
_FILLED_FROM_PARTS = tuple(filter(lambda field: field not in _CANNOT_DO_WITHOUT, _EVERY_FIELD))


def _the_first_refusal_or(read, build):
    refused_pieces = list(filter(_is_refusal, read))
    return _WHETHER_REFUSED[refused_pieces != []](refused_pieces, build)


_WHETHER_REFUSED = {True: lambda refused_pieces, _build: refused_pieces[0], False: lambda _r, build: build()}


def _nothing_names_it(part):
    return refused("missing_part",
                   f"this question names no {part}, and a declaration cannot be built without one",
                   {"missing": part})


def _whatever_is_missing(asked):
    return [_nothing_names_it(part) for part in filter(lambda p: asked.get(p) is NOTHING, _CANNOT_DO_WITHOUT)]


def _no_such_asking_word(word):
    return no_match("asking_words", [word], sorted(WANTED), "no_row_for_the_key", f"wanted {word!r}")


def _whatever_the_word_is(asked):
    word = asked.get("wanted")
    return _WORD_IS_ONE_WE_READ[word in WANTED](word)


_WORD_IS_ONE_WE_READ = {True: lambda word: word, False: _no_such_asking_word}


def _the_condition_in(narrowing):
    return condition_from_narrowing(narrowing)


_HOW_A_FIELD_IS_TURNED = {"condition": _the_condition_in, "having": _the_condition_in}


def _turned(field, said):
    return _FIELD_NEEDS_TURNING[field in _HOW_A_FIELD_IS_TURNED](field, said)


_FIELD_NEEDS_TURNING = {
    True: lambda field, said: _read_or(_HOW_A_FIELD_IS_TURNED, field, lambda: _the_condition_in)(said),
    False: lambda _field, said: said,
}


def _what_the_caller_said(field, asked):
    named = filter(lambda ps: ps[0] in _WHICH_FIELD_EACH_PART_FILLS, asked.items())
    parts = {_read_or(_WHICH_FIELD_EACH_PART_FILLS, part, lambda: part): said for part, said in named}
    return _CALLER_NAMED_IT[field in parts](field, parts)


_CALLER_NAMED_IT = {
    True: lambda field, parts: _turned(field, parts[field]),
    False: lambda field, _parts: _read_or(_WHAT_EMPTY_MEANS, field, lambda: lambda: NOTHING)(),
}


def _built(asked, word):
    filled = {field: _what_the_caller_said(field, asked) for field in _FILLED_FROM_PARTS}
    return _the_first_refusal_or(
        list(filled.values()),
        lambda: {"model": asked["model"], "wanted": word, **filled},
    )


def declaration_from_asked(asked):
    """Turn the parts a reader lifted into the one declaration all four ways of writing build
    (declaration declaration_from_asked). An asking word no row holds answers a NoMatch naming
    asking_words; a part the declaration cannot do without and nobody named is a Fault, one per part."""
    word = _whatever_the_word_is(asked)
    return _the_first_refusal_or([*_whatever_is_missing(asked), word], lambda: _built(asked, word))


# --- asked_from_written (declaration asked_from_written) ---------------------------------------------
# A reduced parser: it finds the model, the asking word, and the narrowing/columns a spelling names,
# over the method names methods_of hands it. A method name no spelling gives a part of a question
# answers a NoMatch naming method_names.
_EVERY_METHOD = ("select", "where", "ordered_by", "grouped_by", "having", "paging", "across", "rows",
                 *WANTED)


def _literal(node):
    """A python literal out of the written text, or the text itself when it is not one."""
    return _try_literal(node)


def _try_literal(node):
    try:  # honest: ignore HC-P002: reading a literal out of the caller's written query is the parse boundary; a node that is not a literal becomes the text itself, not a raise
        return ast.literal_eval(node)
    except Exception:  # noqa: BLE001
        return NOTHING


def _no_method(method, written):
    return no_match("method_names", [method], list(_EVERY_METHOD), "no_row_for_the_key", written)


def _part_for(method, methods):
    """This library's own name for a method, reading the spelling's own words back through methods."""
    renamed = {spelling_word: own for own, spelling_word in methods.items()}
    return _WHICH_PART[method in renamed](method, renamed)


_WHICH_PART = {
    True: lambda method, renamed: renamed[method],
    False: lambda method, _renamed: method,
}


def _calls(written):
    """Each `name(args)` call in the written chain, as (name, args-source) pairs."""
    found = []
    tree = _parse(written)
    for node in ast.walk(tree):
        _collect_call(node, found)
    return found


def _parse(written):
    try:  # honest: ignore HC-P002: parsing the caller's written query is the parse boundary; a malformed query becomes an empty parse, not a raise
        return ast.parse(written, mode="eval")
    except Exception:  # noqa: BLE001
        return ast.parse("None", mode="eval")


def _collect_call(node, found):
    is_call = isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    _pick(is_call, lambda: _record_call(node, found), lambda: None)


def _record_call(node, found):
    found.append((node.func.attr, node.args, node.keywords))


def _model_of(written):
    """The leftmost name in the chain, which is the model a caller wrote."""
    tree = _parse(written)
    names = [n.id for n in filter(lambda n: isinstance(n, ast.Name), ast.walk(tree))]
    return next(iter(names), NOTHING)


def _asked(model, parts):
    return {"model": model, **parts}


def asked_from_written(written, methods):
    """Read the writing and lift the parts out (declaration asked_from_written): a model, then the calls
    that carry the asking word and the parts of the question, in the library's own words. A method name
    no spelling gives any part answers a NoMatch naming method_names."""
    model = _model_of(written)
    calls = _calls(written)
    parts = {}
    wanted = NOTHING
    for name, args, keywords in calls:
        part = _part_for(name, methods)
        wanted = _WANTED_OR_KEEP[part in WANTED](part, wanted)
        parts.update(_part_value(part, args, keywords))
    tail = _tail_word(written)
    wanted = _WANTED_OR_KEEP[tail in WANTED](tail, wanted)
    return _asked(model, {**parts, "wanted": wanted})


_WANTED_OR_KEEP = {True: lambda part, _wanted: part, False: lambda _part, wanted: wanted}


def _part_value(part, args, keywords):
    """What a part carries, read off its call's args or keywords."""
    from_kw = {kw.arg: _literal(kw.value) for kw in keywords}
    from_args = [_literal(a) for a in args]
    return _PART_SHAPE[part in ("where", "having")](part, from_args, from_kw)


_PART_SHAPE = {
    True: lambda part, _args, kw: {part: kw or {}},
    False: lambda part, args, _kw: _ROWS_STAY_LISTED[part == "rows"](part, args),
}

# rows is always a list of row-dicts, so a single `.rows({...})` is `[{...}]`, never the bare dict;
# every other part collapses a lone argument to the bare value.
_ROWS_STAY_LISTED = {
    True: lambda part, args: _pick(bool(args), lambda: {part: args}, lambda: {}),
    False: lambda part, args: _pick(bool(args), lambda: {part: _pick(len(args) == 1, lambda: args[0], lambda: args)}, lambda: {}),
}


def _tail_word(written):
    """A trailing attribute with no call, like `.all`, is the asking word in pseudo_sql."""
    stripped = written.rstrip()
    last = stripped.rsplit(".", 1)[-1]
    return _TAIL[last in WANTED](last)


_TAIL = {True: lambda last: last, False: lambda _last: NOTHING}
