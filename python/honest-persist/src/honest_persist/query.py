"""Query builders (section 7.2): a query is data, building it is a pure function.

`select` / `insert` / `update` / `delete` / `raw` each return a Query — `{sql, params}` —
and perform no I/O. There is no method chaining that hides execution: the query is
inspectable, loggable, and serializable before it runs. Parameters are always named
(`:name`), never positional, and `params` is the complete set, so no escaping is needed at
the call site. Executing a Query is section 7.4's boundary concern, not this module's.

Mutating persisted state is not done with a bare `update`/`delete` here — that is section
7.5's guarded primitive. These builders produce the parameterized SQL the rest of the layer
(and guarded mutation) compiles around.
"""

from honest_persist.types import Query


def _query(sql: str, params: dict) -> Query:
    return {"sql": sql, "params": params}


def _where_clause(where) -> tuple[str, dict]:
    """A WHERE clause (ANDed equality) and its params from {column: value}, or ('', {})."""
    if not where:
        return "", {}
    conditions = " AND ".join(f"{column} = :{column}" for column in where)
    return " WHERE " + conditions, dict(where)


def _order_clause(order_by) -> str:
    """ORDER BY from a list of columns; a leading '-' marks DESC, otherwise ASC."""
    if not order_by:
        return ""
    terms = [f"{c[1:]} DESC" if c.startswith("-") else f"{c} ASC" for c in order_by]
    return " ORDER BY " + ", ".join(terms)


def _join_clause(joins) -> str:
    """JOINs from a list of {table, on} specs."""
    if not joins:
        return ""
    return "".join(f" JOIN {spec['table']} ON {spec['on']}" for spec in joins)


def select(table, columns=None, where=None, order_by=None, limit=None, offset=None, joins=None) -> Query:
    """A SELECT Query (section 7.2). Pure."""
    column_list = ", ".join(columns) if columns else "*"
    where_sql, params = _where_clause(where)
    sql = f"SELECT {column_list} FROM {table}{_join_clause(joins)}{where_sql}{_order_clause(order_by)}"
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit
    if offset is not None:
        sql += " OFFSET :offset"
        params["offset"] = offset
    return _query(sql, params)


def insert(table, values) -> Query:
    """An INSERT Query (section 7.2). Pure."""
    columns = list(values)
    column_list = ", ".join(columns)
    placeholders = ", ".join(f":{column}" for column in columns)
    return _query(f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", dict(values))


def update(table, values, where) -> Query:
    """An UPDATE Query (section 7.2). Pure. SET params are prefixed `set_` so they never
    collide with a WHERE param on the same column."""
    set_clause = ", ".join(f"{column} = :set_{column}" for column in values)
    params = {f"set_{column}": value for column, value in values.items()}
    where_sql, where_params = _where_clause(where)
    params.update(where_params)
    return _query(f"UPDATE {table} SET {set_clause}{where_sql}", params)


def delete(table, where) -> Query:
    """A DELETE Query (section 7.2). Pure."""
    where_sql, params = _where_clause(where)
    return _query(f"DELETE FROM {table}{where_sql}", params)


def raw(sql, params=None) -> Query:
    """A raw SQL Query carrying named params (section 7.2). The escape hatch — still data."""
    return _query(sql, dict(params or {}))
