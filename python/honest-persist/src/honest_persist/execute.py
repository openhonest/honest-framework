"""Query execution (section 7.4): the I/O boundary where a built Query meets the database.

Building a Query is pure (query.py); running it is I/O and lives only here. Each function
takes a Query and a connection and returns plain data — a list of row dicts, one row, a
single scalar, or a rows-affected count. No ORM: what comes back is plain dicts, nothing more.

The connection is duck-typed, as in apply.py (section 5.2): `conn.execute(sql, params)`
returns `{"rows": [row, ...], "rowcount": int}`. The reference implementation realizes these
functions synchronously; the host language may make them async where its driver is. Driver
errors are not caught here — they propagate to the outer boundary (honest-type
`catch_at_boundary`), the one sanctioned place a fault is turned back into output.
"""

from honest_persist.types import Query


def execute(query: Query, conn) -> list:
    """Run a Query and return every row as a plain dict (section 7.4). I/O."""
    return conn.execute(query["sql"], query["params"])["rows"]


def execute_one(query: Query, conn):
    """Run a Query and return its first row, or None when there are none (section 7.4). I/O."""
    rows = conn.execute(query["sql"], query["params"])["rows"]
    return rows[0] if rows else None


def execute_scalar(query: Query, conn):
    """Run a Query and return the first column of the first row, or None (section 7.4). I/O."""
    rows = conn.execute(query["sql"], query["params"])["rows"]
    if not rows:
        return None
    return next(iter(rows[0].values()))


def execute_many(query: Query, conn) -> int:
    """Run a Query and return the number of rows it affected (section 7.4). I/O."""
    return conn.execute(query["sql"], query["params"])["rowcount"]
