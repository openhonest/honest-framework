"""Query builders (section 7.2) and schema-checked building (section 7.3).

`select` / `insert` / `update` / `delete` / `raw` each return a Query — `{sql, params}` —
and perform no I/O. There is no method chaining that hides execution: the query is
inspectable, loggable, and serializable before it runs. Parameters are always named
(`:name`), never positional, and `params` is the complete set, so no escaping is needed at
the call site. Executing a Query is section 7.4's boundary concern, not this module's.

The `checked_*` builders (section 7.3) take a Schema first and return a Result: `ok(Query)`
when every table and column the query names is declared, or `err(fault)` listing what was
not found. Pure: validation is against the declared schema, not the live database, so a
misspelled column is caught at build time rather than reaching the database in production.
"""

from honest_type import err, fault, ok

from honest_persist.check import enforce_checks
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


def _declared_columns(schema, table):
    """The set of column names declared for `table`, or None when the table is undeclared."""
    if table not in schema:
        return None
    return set(schema[table].get("columns", {}))


def _unknown_columns(declared, names) -> list:
    """The referenced names not in `declared`, ignoring the `*` wildcard and an ORDER BY
    `-` (descending) prefix. Sorted, so the fault is deterministic."""
    referenced = {name[1:] if name.startswith("-") else name for name in names if name != "*"}
    return sorted(referenced - declared)


def _check_columns(schema, table, names):
    """ok(table) when `table` and every referenced column is declared; else err(fault)
    (section 7.3). Pure."""
    declared = _declared_columns(schema, table)
    if declared is None:
        return err(fault("unknown_table", f"Table '{table}' is not declared in the schema", "server", {"table": table}))
    unknown = _unknown_columns(declared, names)
    if unknown:
        return err(
            fault(
                "unknown_column",
                f"Column(s) {unknown} not declared on table '{table}'",
                "server",
                {"table": table, "columns": unknown, "declared": sorted(declared)},
            )
        )
    return ok(table)


def checked_select(schema, table, columns=None, where=None, order_by=None, joins=None, limit=None, offset=None):
    """A schema-checked SELECT (section 7.3): ok(Query) or err(fault). Pure."""
    checked = _check_columns(schema, table, list(columns or []) + list(where or []) + list(order_by or []))
    if "err" in checked:
        return checked
    for spec in joins or []:
        if spec["table"] not in schema:
            return err(
                fault("unknown_table", f"Join table '{spec['table']}' is not declared in the schema", "server", {"table": spec["table"]})
            )
    return ok(select(table, columns=columns, where=where, order_by=order_by, joins=joins, limit=limit, offset=offset))


def checked_insert(schema, table, values, dialect="postgresql"):
    """A schema-checked INSERT (section 7.3): ok(Query) or err(fault). Pure. As well as checking every
    column is declared, it enforces the table's CHECK constraints on the row for the target `dialect`
    (section 6.2): on a dialect that does not enforce CHECK natively, a violating row is refused here
    rather than reaching a database that would silently accept it. `dialect` defaults to a native one,
    so the database is trusted unless a non-native dialect is named."""
    checked = _check_columns(schema, table, list(values))
    if "err" in checked:
        return checked
    enforced = enforce_checks(schema, table, values, dialect)
    if "err" in enforced:
        return enforced
    return ok(insert(table, values))


def checked_update(schema, table, values, where):
    """A schema-checked UPDATE (section 7.3): ok(Query) or err(fault). Pure."""
    checked = _check_columns(schema, table, list(values) + list(where or []))
    if "err" in checked:
        return checked
    return ok(update(table, values, where))


def checked_delete(schema, table, where):
    """A schema-checked DELETE (section 7.3): ok(Query) or err(fault). Pure."""
    checked = _check_columns(schema, table, list(where or []))
    if "err" in checked:
        return checked
    return ok(delete(table, where))
