"""Query execution (section 7.4): the I/O boundary where a built Query meets the database.

Building a Query is pure (query.py); running it is I/O and lives only here. Each function
takes a Query and a connection and returns plain data — a list of row dicts, one row, a
single scalar, or a rows-affected count. No ORM: what comes back is plain dicts, nothing more.

These functions are async: a synchronous database call is the deprecated pattern, so the
boundary awaits the driver. The connection is duck-typed: `await conn.execute(sql, params)`
returns `{"rows": [row, ...], "rowcount": int}`. Driver errors are not caught here — they
propagate to the outer boundary (honest-type `catch_at_boundary`), the one sanctioned place a
fault is turned back into output.
"""

from honest_persist.types import Query


async def execute(query: Query, conn) -> list:
    """Run a Query and return every row as a plain dict (section 7.4). I/O."""
    result = await conn.execute(query["sql"], query["params"])
    return result["rows"]


async def execute_one(query: Query, conn):
    """Run a Query and return its first row, or None when there are none (section 7.4). I/O."""
    result = await conn.execute(query["sql"], query["params"])
    rows = result["rows"]
    return rows[0] if rows else None


async def execute_scalar(query: Query, conn):
    """Run a Query and return the first column of the first row, or None (section 7.4). I/O."""
    result = await conn.execute(query["sql"], query["params"])
    rows = result["rows"]
    if not rows:
        return None
    return next(iter(rows[0].values()))


async def execute_many(query: Query, conn) -> int:
    """Run a Query and return the number of rows it affected (section 7.4). I/O."""
    result = await conn.execute(query["sql"], query["params"])
    return result["rowcount"]
