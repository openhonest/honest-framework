"""The §7 query layer: five pure builders and five I/O executors, a path of its own.

A query is data (spec §7.1). Building one is a pure function that answers a `Query` — a dict carrying
the parameterized `sql` text and the complete named-parameter set `params` — and does no I/O (spec §7.2).
Running one is I/O at a single boundary: an executor takes a `Query` and a connection the caller supplies
and owns, and awaits `conn.execute(sql, params)`, which answers `{rows, rowcount}` (spec §7.4). These are
always separate steps.

This layer is dialect-agnostic and connection-agnostic and does not touch the engine machinery (io.py,
query.py, _compile.py): it imports no driver, holds no session, and reaches the database only through the
duck-typed connection the caller hands in (declaration QueryConnection, spec §8.1.1). The builders emit
sqlite-runnable **named** parameters — `:name` with `params` keyed to match — so a real driver binds every
value and the caller escapes nothing at the call site (spec §7.2). Where an UPDATE's SET keys and its WHERE
keys could collide, the SET params are prefixed `s_` and the WHERE params `w_`, so one column named in both
halves still carries two distinct values.

Every optional part of a SELECT is an explicit NOTHING when absent, never a language default (P15): a caller
that named nothing and one that chose nothing read the same. The file carries no `if`: a branch is a boolean
key looked up through `_pick` (HC-P001). The executors are the layer's only I/O and do not catch — a driver
error propagates to honest-type's `catch_at_boundary` (P08) — except `transaction`, the one sanctioned catch,
which must see a write fail to roll the whole group back (spec §7.5, modelled on `apply`).
"""

from honest_persist._util import _pick
from honest_persist.types import is_fault, refused

NOTHING = None


# --- the pure builders (spec §7.2): names in, a Query out, no I/O -------------------------------------

def select(table, columns, where, order_by, limit, offset, joins):
    """Build a SELECT Query from names (declaration select, spec §7.2). NOTHING columns means all of them
    (`*`); a NOTHING or empty `where` means no filter; NOTHING order_by, limit, offset and joins each mean
    that clause is absent. Every value in `where` is carried in the Query's named `params`, prefixed `w_`."""
    where_sql, params = _where(where or {})
    sql = "".join([
        "SELECT ", ", ".join(columns or ["*"]),
        " FROM ", table,
        _joins(joins or []),
        where_sql,
        _order(order_by or []),
        _limit(limit),
        _offset(offset),
    ])
    return {"sql": sql, "params": params}


def insert(table, values):
    """Build an INSERT Query (declaration insert, spec §7.2): every value is carried in `params`, keyed by
    its column name, so the driver binds it. No collision can arise — an insert carries one set of names."""
    columns = ", ".join(values)
    placeholders = ", ".join(f":{column}" for column in values)
    sql = "".join(["INSERT INTO ", table, " (", columns, ") VALUES (", placeholders, ")"])
    return {"sql": sql, "params": dict(values)}


def update(table, values, where):
    """Build an UPDATE Query (declaration update, spec §7.2). The SET params are prefixed `s_` and the WHERE
    params `w_`, so a column named in both the new values and the filter carries two distinct bound values.
    An empty `where` sets every row."""
    set_sql, set_params = _assignments(values)
    where_sql, where_params = _where(where or {})
    sql = "".join(["UPDATE ", table, " SET ", set_sql, where_sql])
    return {"sql": sql, "params": {**set_params, **where_params}}


def delete(table, where):
    """Build a DELETE Query (declaration delete, spec §7.2): every filter value is carried in `params`,
    prefixed `w_`. An empty `where` deletes every row."""
    where_sql, params = _where(where or {})
    sql = "".join(["DELETE FROM ", table, where_sql])
    return {"sql": sql, "params": params}


def raw(sql, params):
    """Build a Query from SQL the caller wrote (declaration raw, spec §7.2): the one builder carrying no
    column names to check. NOTHING params becomes an empty set."""
    return {"sql": sql, "params": params or {}}


# --- the schema-checked builders (spec §7.3): a pure name-check, then the raw builder ------------------
# Each takes the declared Schema first, checks every name the query uses against it, and either returns
# the module's bare-union Fault or defers to its raw §7.2 sibling, so checked and raw never diverge. The
# check is pure: it reads the declared tables and columns, touches no connection and does no I/O (P03).

def checked_select(schema, table, columns, where, order_by, limit, offset, joins):
    """Build a SELECT Query exactly as select does, after checking every name against the declared schema
    (declaration checked_select, spec §7.3). The table and every join's table must be declared, and the
    selected columns, the where keys and the order_by keys (its `-` prefix stripped, its `*` skipped) must
    be declared columns of the table; else a bare-union unknown_table or unknown_column Fault. On success
    it returns exactly the Query select builds from the same arguments."""
    problem = _check(schema, [table] + _join_tables(joins), _select_names(columns, where, order_by), table)
    return _pick(is_fault(problem),
                 lambda: problem,
                 lambda: select(table, columns, where, order_by, limit, offset, joins))


def checked_insert(schema, table, values):
    """Build an INSERT Query exactly as insert does, after checking its names (declaration checked_insert,
    spec §7.3): the table must be declared and every key of values a declared column, else a bare-union
    unknown_table or unknown_column Fault. On success it returns exactly the Query insert builds."""
    problem = _check(schema, [table], _keys(values), table)
    return _pick(is_fault(problem), lambda: problem, lambda: insert(table, values))


def checked_update(schema, table, values, where):
    """Build an UPDATE Query exactly as update does, after checking its names (declaration checked_update,
    spec §7.3): the table must be declared and every key of values and of where a declared column, else a
    bare-union unknown_table or unknown_column Fault. On success it returns exactly update's Query."""
    problem = _check(schema, [table], _keys(values) + _keys(where), table)
    return _pick(is_fault(problem), lambda: problem, lambda: update(table, values, where))


def checked_delete(schema, table, where):
    """Build a DELETE Query exactly as delete does, after checking its names (declaration checked_delete,
    spec §7.3): the table must be declared and every key of where a declared column, else a bare-union
    unknown_table or unknown_column Fault. On success it returns exactly the Query delete builds."""
    problem = _check(schema, [table], _keys(where), table)
    return _pick(is_fault(problem), lambda: problem, lambda: delete(table, where))


# --- the name-check, shared by all four builders (spec §7.3): tables exist, columns are declared -------

def _check(schema, tables, column_names, column_table):
    """A Fault when any of `tables` is not a declared table (unknown_table, naming the first one missing)
    or any of `column_names` is not a declared column of `column_table` (unknown_column), else NOTHING.
    Table existence is read before columns, so a query against a table no schema holds is unknown_table
    rather than a column miss against a table that is not there."""
    def _table_named(schema, name):
        """The declared Table named `name`, or NOTHING when the schema holds no such table."""
        matches = list(filter(lambda t: t["name"] == name, schema["tables"]))
        return _pick(bool(matches), lambda: matches[0], lambda: NOTHING)

    def _check_columns(schema, table, column_names):
        """A Fault when any of `column_names` is not a declared column of the (already-confirmed) `table`,
        else NOTHING. The fault's detail carries the table, the names not found, and the columns the table
        declares, so a caller reads the mismatch as data (P25)."""
        declared = _declared_columns(_table_named(schema, table))
        missing = list(filter(lambda name: name not in declared, column_names))
        return _pick(bool(missing),
                     lambda: _unknown_column(table, missing, declared),
                     lambda: NOTHING)

    missing_tables = list(filter(lambda name: _table_named(schema, name) is NOTHING, tables))
    return _pick(bool(missing_tables),
                 lambda: _unknown_table(missing_tables[0]),
                 lambda: _check_columns(schema, column_table, column_names))


# The names of the columns the table declares.
_declared_columns = lambda table: [column["name"] for column in table["columns"]]


# The table each join reads, so a join's named table is checked for existence the same as the main
# table; a NOTHING joins means no joins, hence no further tables to check (declaration checked_select).
_join_tables = lambda joins: [join["table"] for join in (joins or [])]


# Every column name a SELECT uses that must be declared: the selected columns (the `*` wildcard
# skipped, NOTHING meaning all columns and so nothing to check), the where keys, and the order_by keys
# with their leading `-` descending marker stripped before checking (declaration checked_select).
_select_names = lambda columns, where, order_by: _columns_named(columns) + _keys(where) + _order_names(order_by)


# The selected column names to check: NOTHING means all columns (nothing to check) and the `*`
# wildcard is skipped, the two parts §7.3 recognises and does not column-check.
_columns_named = lambda columns: list(filter(lambda column: column != "*", columns or []))


# The order_by column names to check, each with its leading `-` descending marker stripped first.
_order_names = lambda order_by: [_strip_descending(column) for column in (order_by or [])]


# A `-`-prefixed order_by key names its column descending; the name to check is that key without the
# marker (declaration checked_select, mirroring _order_term's own `-` reading).
_strip_descending = lambda column: _pick(column.startswith("-"), lambda: column[1:], lambda: column)


# The keys of a (possibly NOTHING) column-to-value map, as the column names to check.
_keys = lambda mapping: list((mapping or {}).keys())


# The bare-union Fault for a table no schema declares (declaration checked_select, spec §7.3): name a
# declared table instead, the one named here is not one.
_unknown_table = lambda table: refused(
    "unknown_table",
    f"table {table!r} is not a declared table; name a table the schema declares instead",
    {"table": table},
)


# The bare-union Fault for columns no table declares (declaration checked_select, spec §7.3): name
# columns the table declares instead. The detail carries the offending columns and the declared ones so
# a caller reads the mismatch as data (P25).
_unknown_column = lambda table, columns, declared: refused(
    "unknown_column",
    f"columns {columns} are not declared on table {table!r}; name columns it declares instead: {declared}",
    {"table": table, "columns": columns, "declared": declared},
)


# --- the clause builders the SELECT assembles, each if-free --------------------------------------------

# A WHERE clause and its params from a (possibly empty) column-to-value map. Empty means no filter,
# answered as an empty clause and empty params; otherwise `WHERE c = :w_c AND ...` with params `w_c`.
_where = lambda where: _pick(bool(where), lambda: _where_clause(where), lambda: ("", {}))


_where_clause = lambda where: (
    " WHERE " + " AND ".join(f"{column} = :w_{column}" for column in where),
    {f"w_{column}": where[column] for column in where},
)


# The SET fragment and its `s_`-prefixed params for an UPDATE.
_assignments = lambda values: (
    ", ".join(f"{column} = :s_{column}" for column in values),
    {f"s_{column}": values[column] for column in values},
)


# The JOIN fragments for a (possibly empty) list of QueryJoins; empty answers an empty string. The ON
# expression is raw SQL and is never column-checked, the same boundary raw() draws (declaration QueryJoin).
_joins = lambda joins: "".join(f" JOIN {join['table']} ON {join['on']}" for join in joins)


# The ORDER BY fragment for a (possibly empty) list of columns; empty answers an empty string. A `-`
# prefix on a column sorts it descending (declaration select).
_order = lambda order_by: _pick(bool(order_by),
                                lambda: " ORDER BY " + ", ".join(_order_term(column) for column in order_by),
                                lambda: "")


_order_term = lambda column: _pick(column.startswith("-"), lambda: f"{column[1:]} DESC", lambda: column)


# The LIMIT fragment; NOTHING answers an empty string (declaration select).
_limit = lambda limit: _pick(limit is None, lambda: "", lambda: f" LIMIT {limit}")


# The OFFSET fragment; NOTHING answers an empty string (declaration select).
_offset = lambda offset: _pick(offset is None, lambda: "", lambda: f" OFFSET {offset}")


# --- the executors (spec §7.4-§7.5): I/O at one boundary over the caller's connection -------------------

async def execute(query, conn):
    """Run a query on the caller's connection and answer its rows, each a plain dict (declaration execute,
    spec §7.4). It does not catch: a driver error propagates to honest-type's catch_at_boundary (P08)."""
    result = await conn.execute(query["sql"], query["params"])
    return result["rows"]


async def execute_one(query, conn):
    """Run a query and answer its first row, or NOTHING when it returned none (declaration execute_one,
    spec §7.4). It does not catch (P08)."""
    result = await conn.execute(query["sql"], query["params"])
    rows = result["rows"]
    return _pick(bool(rows), lambda: rows[0], lambda: NOTHING)


async def execute_scalar(query, conn):
    """Run a query and answer the first cell of its first row, or NOTHING when it returned no rows — a NULL
    cell is not told apart from no rows (declaration execute_scalar, spec §7.4). It does not catch (P08)."""
    result = await conn.execute(query["sql"], query["params"])
    rows = result["rows"]
    return _pick(bool(rows), lambda: _first_cell(rows[0]), lambda: NOTHING)


_first_cell = lambda row: next(iter(row.values()))


async def execute_many(query, conn):
    """Run a write query and answer the rows-affected count the driver reported (declaration execute_many,
    spec §7.4). It does not catch (P08)."""
    result = await conn.execute(query["sql"], query["params"])
    return result["rowcount"]


async def transaction(writes, conn):
    """Run several writes as one all-or-nothing step on the caller's connection (declaration transaction,
    spec §7.5): begin, run each write collecting its rows-affected count in arrival order, then commit and
    answer the list of counts. On a driver error it rolls back and answers the module's bare-union Fault
    `write_failed`, naming the failing write's index and the driver's text — the one sanctioned catch here."""
    async def _attempt_write(write, index, conn):
        try:  # honest: ignore HC-P002: the transaction boundary catches the driver's throw, rolls back, and returns it as a write_failed Fault value — the one sanctioned catch here, as apply does (P08, spec 7.5)
            result = await conn.execute(write["sql"], write["params"])
            return result["rowcount"]
        except Exception as failed:  # noqa: BLE001
            await conn.rollback()
            return refused(
                "write_failed",
                f"the write at index {index} was refused and the whole transaction rolled back: {failed}",
                {"failed_at": index, "message": str(failed)},
            )

    async def _rolled_back(fault):
        return fault

    async def _commit(conn, counts):
        await conn.commit()
        return counts

    async def _write_then_continue(writes, index, conn, counts):
        outcome = await _attempt_write(writes[index], index, conn)
        return await _pick(is_fault(outcome),
                           lambda: _rolled_back(outcome),
                           lambda: _drain_writes(writes, index + 1, conn, counts + [outcome]))

    async def _drain_writes(writes, index, conn, counts):
        return await _pick(index >= len(writes),
                           lambda: _commit(conn, counts),
                           lambda: _write_then_continue(writes, index, conn, counts))

    await conn.begin()
    return await _drain_writes(writes, 0, conn, [])
