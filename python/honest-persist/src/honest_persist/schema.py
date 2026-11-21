"""The schema-declaration leaves of the declaration: field, schema_from_declared, migration_needed.

Pure, if-free, data in and data out, no state of their own. These three are the structural half of
the schema layer: `field` records the two facts a column annotation cannot carry, `schema_from_declared`
builds the target schema the host's models want, and `migration_needed` says whether a live schema
still has to be brought up to that target. Every mapping here is fixed by the declaration's types
(honest-persist.hd) and spec section 5; none consults anything but its arguments.
"""


def field(renamed_from, references):
    """Build the two-fact record a host says about one column beside its annotation (declaration
    `type Field`, `fn field`): what the column was renamed from, and where it points. Neither argument
    has a default, because a column that forgot to say where it points and one that points nowhere are
    different facts and only the host knows which; both are the named absence (None) when the host
    leaves them unsaid. Both facts carry through exactly as handed in, so nothing a second naming could
    drift from is invented here."""
    return {"renamed_from": renamed_from, "references": references}


def _table_from_model(model):
    """One Model becomes one Table (declaration `type Model`, `type Table`; spec 5.1). The target
    schema names a table by the model's `table`, not its `name`, because a live schema read back from
    a database names it that way, and carries the model's columns, indexes and constraints as they
    stand. The model's `name` and `dropping` are the differ's business and are not fields of a table."""
    return {
        "name": model["table"],
        "columns": model["columns"],
        "indexes": model["indexes"],
        "constraints": model["constraints"],
    }


def schema_from_declared(declared):
    """Build the target Schema from what the code declares, and from nothing else (declaration
    `fn schema_from_declared`; spec 5.1): each Model becomes a Table, and the declared views carry over
    unchanged. An empty declaration builds an empty schema, which is an answer and not a failure."""
    return {
        "tables": [_table_from_model(model) for model in declared["models"]],
        "views": declared["views"],
    }


def migration_needed(live, target):
    """Answer whether the database still has to be brought up to the models (declaration
    `fn migration_needed`; migration_compare boundary, spec line 116): a live schema already matching
    the wanted one needs no migration, and any difference between the two needs one. The comparison is
    structural — the two schemas are equal or they are not — and the engine's own tables are already
    left out of the live schema by the inspection questions, so nothing here has to exclude them."""
    return live != target


from operator import itemgetter  # noqa: E402

from honest_persist._util import _pick, _read_or  # noqa: E402
from honest_persist.types import refused  # noqa: E402

NOTHING = None

# --- the difference between two schemas (declaration difference, spec section 5) --------------------
_DESTROYS = {
    "create_table": False, "drop_table": True, "add_column": False, "drop_column": True,
    "alter_column": True, "rename_column": False, "rename_table": False, "create_index": False,
    "drop_index": False, "create_view": False, "drop_view": False, "refresh_view": False,
    "insert_enum_values": False, "remove_enum_values": True,
}


def _operation(kind, name, column, columns, indexes, constraints, copying, values, renamed_to, view):
    """One operation, carrying everything its kind names and whether it destroys."""
    return {
        "kind": kind, "table": name, "column": column, "columns": columns, "indexes": indexes,
        "constraints": constraints, "copying": copying, "values": values, "renamed_to": renamed_to,
        "view": view, "destroys": _read_or(_DESTROYS, kind, lambda: False),
    }


def _by_name(items):
    """Tables, columns or views under their own names, so a comparison is three set operations."""
    return {item["name"]: item for item in items}


def _rules_on(column, table):
    """Every rule this table declares about this column, as kind and value, sorted so list order is not
    a difference and nameless, because the engine makes up names for unnamed rules."""
    return sorted(
        (rule["kind"], repr(rule["value"]))
        for rule in filter(lambda r: column in r["columns"], table["constraints"])
    )


def _differs(column, live, target, held, wanted):
    """Whether the live column and the declared one are the same column: its type and every rule."""
    return held[column]["declared_type"] != wanted[column]["declared_type"] or _rules_on(column, live) != _rules_on(column, target)


def _columns_of(live, target):
    """What turns one table's live columns into its declared ones."""
    name = target["name"]
    held = _by_name(live["columns"])
    wanted = _by_name(target["columns"])
    carried_across = list(filter(lambda c: c in held, wanted))
    added = [
        _operation("add_column", name, column, [wanted[column]], [], target["constraints"], [], [], None, None)
        for column in filter(lambda c: c not in held, wanted)
    ]
    dropped = [
        _operation("drop_column", name, column, target["columns"], target["indexes"],
                   target["constraints"], carried_across, [], None, None)
        for column in filter(lambda c: c not in wanted, held)
    ]
    altered = [
        _operation("alter_column", name, column, target["columns"], target["indexes"],
                   target["constraints"], carried_across, [], None, None)
        for column in filter(lambda c: c in held and _differs(c, live, target, held, wanted), wanted)
    ]
    return added + dropped + altered


def _views_of(live, target):
    """What turns the live views into the declared ones; a changed one is a drop and a create."""
    held = _by_name(live["views"])
    wanted = _by_name(target["views"])
    created = [
        _operation("create_view", name, None, [], [], [], [], [], None, wanted[name])
        for name in filter(lambda n: n not in held, wanted)
    ]
    dropped = [
        _operation("drop_view", name, None, [], [], [], [], [], None, held[name])
        for name in filter(lambda n: n not in wanted, held)
    ]
    replaced = [
        operation
        for name in filter(lambda n: n in held and held[n] != wanted[n], wanted)
        for operation in (
            _operation("drop_view", name, None, [], [], [], [], [], None, held[name]),
            _operation("create_view", name, None, [], [], [], [], [], None, wanted[name]),
        )
    ]
    return created + dropped + replaced


def difference(live, target):
    """Work out which operations turn the live schema into the target (declaration difference): set
    theory over two schemas, what is only in the target created, what is only live dropped, what differs
    altered. No engine appears; the list is in the order it was worked out, not a running order."""
    held = _by_name(live["tables"])
    wanted = _by_name(target["tables"])
    created = [
        _operation("create_table", name, None, wanted[name]["columns"], wanted[name]["indexes"],
                   wanted[name]["constraints"], [], [], None, None)
        for name in filter(lambda n: n not in held, wanted)
    ]
    dropped = [
        _operation("drop_table", name, None, [], [], [], [], [], None, None)
        for name in filter(lambda n: n not in wanted, held)
    ]
    columns = [
        operation
        for name in filter(lambda n: n in held, wanted)
        for operation in _columns_of(held[name], wanted[name])
    ]
    return created + dropped + columns + _views_of(live, target)


# --- ordering the operations their dependencies allow (declaration order_operations) -----------------
def _nothing_of_its_own(_operation):
    return ()


def _its_own_table(operation):
    return (operation["table"],)


_MUST_ALREADY_EXIST = {
    "create_table": _nothing_of_its_own, "drop_table": _its_own_table, "add_column": _its_own_table,
    "drop_column": _its_own_table, "alter_column": _its_own_table, "rename_column": _its_own_table,
    "rename_table": _its_own_table, "create_index": _its_own_table, "drop_index": _its_own_table,
    "create_view": _its_own_table, "drop_view": _its_own_table, "refresh_view": _its_own_table,
    "insert_enum_values": _its_own_table, "remove_enum_values": _its_own_table,
}


def _needed_by(operation):
    """The tables that have to exist while this operation runs."""
    pointed_at = tuple(sorted({
        column["references"]["table"]
        for column in filter(lambda c: c["references"] is not None, operation["columns"])
    }))
    return _MUST_ALREADY_EXIST[operation["kind"]](operation) + pointed_at


def _positions_of(operations, kind):
    return {
        operation["table"]: position
        for position, operation in filter(lambda io: io[1]["kind"] == kind, enumerate(operations))
    }


def _needs(operations):
    return [(position, name) for position, operation in enumerate(operations) for name in _needed_by(operation)]


def _must_run_before(operations):
    """Where each operation was written, and what has to run before it."""
    makes = _positions_of(operations, "create_table")
    ends = _positions_of(operations, "drop_table")
    needs = _needs(operations)
    edges = [
        (makes[name], position)
        for position, name in filter(lambda pn: pn[1] in makes and makes[pn[1]] != pn[0], needs)
    ] + [
        (position, ends[name])
        for position, name in filter(lambda pn: pn[1] in ends and ends[pn[1]] != pn[0], needs)
    ]
    earlier = {position: set() for position in range(len(operations))}
    for before, after in edges:
        earlier[after].add(before)
    return earlier


def _in_an_order_that_works(operations, placed, _waiting):
    return [operations[position] for position in placed]


def _no_order_works(operations, _placed, waiting):
    circle = "; ".join(
        f"{operations[position]['kind']} on {operations[position]['table']} comes after "
        + ", ".join(operations[source]["table"] for source in sorted(sources))
        for position, sources in sorted(waiting.items())
    )
    return refused(
        "cyclic_operations",
        f"these operations depend on each other in a circle, so no order runs them all: {circle}. "
        f"Break the circle in the models: take one of the references off.",
        {"cycle": circle},
    )


_ORDER_ANSWER = {False: _in_an_order_that_works, True: _no_order_works}


def _free_positions(waiting):
    return sorted(position for position, sources in filter(lambda ps: not ps[1], waiting.items()))


def order_operations(operations):
    """Put the operations in an order their dependencies allow (declaration order_operations); a cycle
    is a Fault. The same list always answers the same way, because no set is ever iterated: operations
    still free are taken in the order they were written."""
    waiting = _must_run_before(operations)
    placed = []
    free = _free_positions(waiting)
    while free:
        position = free[0]
        placed.append(position)
        del waiting[position]
        for sources in waiting.values():
            sources.discard(position)
        free = _free_positions(waiting)
    return _ORDER_ANSWER[bool(waiting)](operations, placed, waiting)


# --- marking what destroys, and refusing an undeclared loss (declaration) ----------------------------
_LOSES_DATA = {
    "create_table": False, "drop_table": True, "add_column": False, "drop_column": True,
    "alter_column": True, "rename_column": False, "rename_table": False, "create_index": False,
    "drop_index": False, "create_view": False, "drop_view": False, "refresh_view": False,
    "insert_enum_values": False, "remove_enum_values": True,
}


def _the_table(operation):
    return operation["table"]


def _the_column(operation):
    return f"{operation['table']}.{operation['column']}"


_NAMES = {
    "create_table": _the_table, "drop_table": _the_table, "add_column": _the_column,
    "drop_column": _the_column, "alter_column": _the_column, "rename_column": _the_column,
    "rename_table": _the_table, "create_index": _the_table, "drop_index": _the_table,
    "create_view": _the_table, "drop_view": _the_table, "refresh_view": _the_table,
    "insert_enum_values": _the_table, "remove_enum_values": _the_table,
}


def _marked(operation):
    """The same operation, carrying the answer about itself: a new dict, not a mutated one."""
    return {**operation, "destroys": _LOSES_DATA[operation["kind"]]}


def name_what_destroys(operations):
    """Mark every operation that loses data, and name what each one loses (declaration
    name_what_destroys)."""
    marked = [_marked(operation) for operation in operations]
    losing = filter(itemgetter("destroys"), marked)
    return {"operations": marked, "destroys": [_NAMES[operation["kind"]](operation) for operation in losing]}


def _columns_this_table_means_to_lose(table, declared):
    return [
        column
        for model in filter(lambda m: m["table"] == table, declared["models"])
        for column in model["dropping"]
    ]


def _asked_for(_lost, _to_write):
    return NOTHING


def _nobody_asked(lost, to_write):
    return (lost, to_write)


_PERMITTED = {True: _asked_for, False: _nobody_asked}


def _a_column_dropped(operation, declared):
    table = operation["table"]
    column = str(operation["column"])
    return _PERMITTED[column in _columns_this_table_means_to_lose(table, declared)](
        f"the column {table}.{column}, and every value in it",
        f"Name {column!r} in dropping on the {table} model to lose {table}.{column}.",
    )


def _a_column_narrowed(operation, declared):
    table = operation["table"]
    column = str(operation["column"])
    return _PERMITTED[column in _columns_this_table_means_to_lose(table, declared)](
        f"whatever no longer fits in {table}.{column}",
        f"Name {column!r} in dropping on the {table} model to lose it.",
    )


def _a_table_dropped(operation, declared):
    table = operation["table"]
    return _PERMITTED[table in declared["dropping_tables"]](
        f"the whole of {table}, every row and every column",
        f"Add {table!r} to dropping_tables to lose {table}.",
    )


def _a_view_dropped(operation, declared):
    view = operation["table"]
    return _PERMITTED[view in declared["dropping_views"]](
        f"the view {view}, and anything reading through it",
        f"Add {view!r} to dropping_views to lose {view}.",
    )


def _nothing_declares_this(operation, _declared):
    kind = operation["kind"]
    return _nobody_asked(
        f"whatever a {kind} on {operation['table']} was marked as destroying",
        f"A {kind} loses nothing, so no declaration allows one and this plan cannot be permitted.",
    )


_HOW_A_LOSS_IS_ASKED_FOR = {
    "drop_column": _a_column_dropped, "alter_column": _a_column_narrowed, "drop_table": _a_table_dropped,
    "drop_view": _a_view_dropped, "create_table": _nothing_declares_this, "add_column": _nothing_declares_this,
    "rename_column": _nothing_declares_this, "rename_table": _nothing_declares_this,
    "create_index": _nothing_declares_this, "drop_index": _nothing_declares_this,
    "create_view": _nothing_declares_this, "refresh_view": _nothing_declares_this,
    "insert_enum_values": _nothing_declares_this, "remove_enum_values": _nothing_declares_this,
}


def _let_it_run(plan, _undeclared):
    return plan


def _refuse_loss(_plan, undeclared):
    losses = "; ".join(lost for lost, _to_write in undeclared)
    return refused(
        "undeclared_loss",
        f"bringing the database up to your models would destroy {losses}, and no model asked to lose "
        f"it. {' '.join(to_write for _lost, to_write in undeclared)}",
        {"losses": [lost for lost, _to in undeclared]},
    )


_LOSS_ANSWER = {False: _let_it_run, True: _refuse_loss}


def refuse_undeclared_loss(plan, declared):
    """Stop a migration that would destroy something no declaration asked to lose (declaration
    refuse_undeclared_loss), naming the table and what to declare to allow it."""
    said_for_each = [
        _HOW_A_LOSS_IS_ASKED_FOR[operation["kind"]](operation, declared)
        for operation in filter(itemgetter("destroys"), plan["operations"])
    ]
    undeclared = list(filter(lambda said: said is not NOTHING, said_for_each))
    return _LOSS_ANSWER[undeclared != []](plan, undeclared)


# --- a name the library or an engine owns (declaration refuse_owned_names) ---------------------------
_OWNED_NAMES = {
    "_honest_persist_meta": "the library", "_hp_": "the library", "_honest_persist_tmp_": "the library",
    "sqlite_": "the engine", "turso_": "the engine", "__turso": "the engine",
}


def _nothing_is_wrong(_claims):
    return NOTHING


def _refuse_owned(claims):
    named = "; ".join(
        f"the model {table} declares {name}, and every name starting {prefix} belongs to {_read_or(_OWNED_NAMES, prefix, lambda: '')}"
        for table, name, prefix in claims
    )
    prefixes = ", ".join(sorted({prefix for _table, _name, prefix in claims}))
    return refused(
        "owned_name",
        f"{named}. Rename each to a name that does not start {prefixes}.",
        {"prefixes": sorted({prefix for _t, _n, prefix in claims})},
    )


_OWNED_ANSWER = {False: _nothing_is_wrong, True: _refuse_owned}


def refuse_owned_names(declared):
    """Refuse a model claiming a name the library or an engine owns (declaration refuse_owned_names)."""
    claims = [
        (model["table"], name, prefix)
        for model in declared["models"]
        for name in [model["table"], *(column["name"] for column in model["columns"])]
        for prefix in filter(lambda p: name.casefold().startswith(p), _OWNED_NAMES)
    ]
    return _OWNED_ANSWER[claims != []](claims)


# --- a drop and an add that only the models can tell from a rename (declaration) ---------------------
_STAYS = "stays as it is"
_BECOMES_A_RENAME = "becomes the rename"
_FOLDED_IN = "folded into the rename"


def _each_of_kind(operations, kind):
    """Where it sits, its table and its column, for every operation of one kind."""
    return [
        (at, operation["table"], str(operation["column"]))
        for at, operation in filter(lambda io: io[1]["kind"] == kind, enumerate(operations))
    ]


def _replacements(declared):
    """(table, the column it replaced) -> the column that replaced it, off the models."""
    return {
        (model["table"], str(column["renamed_from"])): column["name"]
        for model in declared["models"]
        for column in filter(lambda c: c["renamed_from"] is not NOTHING, model["columns"])
    }


def _asked_to_lose(declared):
    """(table, column) -> the table, for every column a model means to lose."""
    return {
        (model["table"], column): model["table"]
        for model in declared["models"]
        for column in model["dropping"]
    }


def _a_rename(operation, appeared):
    """The one operation that replaces a gone column and the one that appeared."""
    return {
        "kind": "rename_column", "table": operation["table"], "column": operation["column"],
        "columns": operation["columns"], "indexes": operation["indexes"],
        "constraints": operation["constraints"], "copying": operation["copying"],
        "values": operation["values"], "renamed_to": appeared, "view": operation["view"],
        "destroys": False,
    }


_WHAT_BECOMES_OF_IT = {
    _STAYS: lambda operation, _appeared: [operation],
    _BECOMES_A_RENAME: lambda operation, appeared: [_a_rename(operation, appeared)],
    _FOLDED_IN: lambda _operation, _appeared: [],
}


def _with_renames_made(operations, fate, appeared_as, _ambiguous):
    return [
        built
        for at, operation in enumerate(operations)
        for built in _WHAT_BECOMES_OF_IT[fate[at]](operation, appeared_as[at])
    ]


def _refuse_ambiguous(_operations, _fate, _appeared_as, ambiguous):
    pairs = "; ".join(
        f'"{was}" is gone from {table} and "{now}" has appeared on it'
        for table, was, now in ambiguous
    )
    table, was, now = ambiguous[0]
    return refused(
        "ambiguous_rename",
        f"{pairs}. Either {was} was renamed to {now}, which keeps its rows, or {was} was dropped and "
        f"{now} added, which loses them. Write renamed_from=\"{was}\" on {now}, or name {was} in "
        f"{table}'s dropping.",
        {"ambiguous": ambiguous},
    )


_AMBIGUOUS_ANSWER = {False: _with_renames_made, True: _refuse_ambiguous}


def name_what_is_ambiguous(operations, declared):
    """Turn each declared rename into one operation, and refuse what nothing declares (declaration
    name_what_is_ambiguous). A gone column is settled when the models say another column replaced it, or
    when the model that lost it named it in dropping; a gone column nothing settles, beside a column that
    appeared on the same table, is the pair this refuses."""
    gone = _each_of_kind(operations, "drop_column")
    appeared = _each_of_kind(operations, "add_column")
    replaced_by = _replacements(declared)
    losing = _asked_to_lose(declared)
    arrived = {(table, column): at for at, table, column in appeared}
    renames = {
        (table, column): replaced_by[(table, column)]
        for _at, table, column in filter(
            lambda g: (g[1], g[2]) in replaced_by and (g[1], replaced_by[(g[1], g[2])]) in arrived, gone)
    }
    taken = {(table, appeared_as): was for (table, was), appeared_as in renames.items()}
    unsettled_gone = [
        (table, column)
        for _at, table, column in filter(
            lambda g: (g[1], g[2]) not in renames and (g[1], g[2]) not in losing, gone)
    ]
    unclaimed = [
        (table, column)
        for _at, table, column in filter(lambda a: (a[1], a[2]) not in taken, appeared)
    ]
    ambiguous = [
        (table, was, now)
        for table, was in unsettled_gone
        for far, now in filter(lambda u: u[0] == table, unclaimed)
    ]
    fate = dict.fromkeys(range(len(operations)), _STAYS)
    fate.update({at: _BECOMES_A_RENAME for at, table, column in filter(lambda g: (g[1], g[2]) in renames, gone)})
    fate.update({at: _FOLDED_IN for at, table, column in filter(lambda a: (a[1], a[2]) in taken, appeared)})
    appeared_as = dict.fromkeys(range(len(operations)), "")
    appeared_as.update({at: renames[(table, column)] for at, table, column in filter(lambda g: (g[1], g[2]) in renames, gone)})
    return _AMBIGUOUS_ANSWER[ambiguous != []](operations, fate, appeared_as, ambiguous)
