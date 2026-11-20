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


# --- the clause builders the SELECT assembles, each if-free --------------------------------------------

def _where(where):
    """A WHERE clause and its params from a (possibly empty) column-to-value map. Empty means no filter,
    answered as an empty clause and empty params; otherwise `WHERE c = :w_c AND ...` with params `w_c`."""
    return _pick(bool(where), lambda: _where_clause(where), lambda: ("", {}))


def _where_clause(where):
    terms = " AND ".join(f"{column} = :w_{column}" for column in where)
    params = {f"w_{column}": where[column] for column in where}
    return (" WHERE " + terms, params)


def _assignments(values):
    """The SET fragment and its `s_`-prefixed params for an UPDATE."""
    fragment = ", ".join(f"{column} = :s_{column}" for column in values)
    params = {f"s_{column}": values[column] for column in values}
    return (fragment, params)


def _joins(joins):
    """The JOIN fragments for a (possibly empty) list of QueryJoins; empty answers an empty string. The ON
    expression is raw SQL and is never column-checked, the same boundary raw() draws (declaration QueryJoin)."""
    return "".join(f" JOIN {join['table']} ON {join['on']}" for join in joins)


def _order(order_by):
    """The ORDER BY fragment for a (possibly empty) list of columns; empty answers an empty string. A `-`
    prefix on a column sorts it descending (declaration select)."""
    return _pick(bool(order_by),
                 lambda: " ORDER BY " + ", ".join(_order_term(column) for column in order_by),
                 lambda: "")


def _order_term(column):
    return _pick(column.startswith("-"), lambda: f"{column[1:]} DESC", lambda: column)


def _limit(limit):
    """The LIMIT fragment; NOTHING answers an empty string (declaration select)."""
    return _pick(limit is None, lambda: "", lambda: f" LIMIT {limit}")


def _offset(offset):
    """The OFFSET fragment; NOTHING answers an empty string (declaration select)."""
    return _pick(offset is None, lambda: "", lambda: f" OFFSET {offset}")


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


def _first_cell(row):
    return next(iter(row.values()))


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
    await conn.begin()
    return await _drain_writes(writes, 0, conn, [])


async def _drain_writes(writes, index, conn, counts):
    return await _pick(index >= len(writes),
                       lambda: _commit(conn, counts),
                       lambda: _write_then_continue(writes, index, conn, counts))


async def _commit(conn, counts):
    await conn.commit()
    return counts


async def _write_then_continue(writes, index, conn, counts):
    outcome = await _attempt_write(writes[index], index, conn)
    return await _pick(is_fault(outcome),
                       lambda: _rolled_back(outcome),
                       lambda: _drain_writes(writes, index + 1, conn, counts + [outcome]))


async def _rolled_back(fault):
    return fault


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
