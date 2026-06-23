"""The abstraction layer (section 6): high-level type declarations to ordinary relational structure.

The application declares intent — an enum, a hierarchy, an array, a range — and honest-persist
generates the tables, columns, and constraints that realize it. The whole expansion is one pure
function, `expand_schema`, run before a schema is diffed or applied. Nothing downstream sees an
abstraction: diff, apply, and inspect operate on the relational expansion, subject to exactly the
same verification as any hand-written schema. A column's abstraction is recognized by its declared
`type` and dispatched, by dict lookup, to the expander that rewrites it. This module starts with
ranges (section 6.5); each further abstraction adds an expander to the same table.
"""


def _expand_range(table_name, column_name, column):
    """A range column (section 6.5) to its `{column}_lower` / `{column}_upper` bound columns and the
    `{column}_lower <= {column}_upper` CHECK. Each bound takes the declared `bound_type` and inherits
    the column's nullability. Returns (columns, constraints, generated_tables). Pure."""
    bound = {"type": column.get("bound_type", "integer")}
    if "nullable" in column:
        bound["nullable"] = column["nullable"]
    columns = {column_name + "_lower": dict(bound), column_name + "_upper": dict(bound)}
    constraints = {
        column_name + "_range": {
            "type": "check",
            "expression": column_name + "_lower <= " + column_name + "_upper",
        }
    }
    return columns, constraints, {}


# Each abstraction is recognized by the column's declared `type` and rewritten by its expander
# (section 6). Expanders return (columns, constraints, generated_tables).
_EXPANDERS = {"range": _expand_range}


def _abstraction_kind(column):
    """The abstraction a column declares (section 6), or None for a plain column. Pure."""
    return column.get("type") if column.get("type") in _EXPANDERS else None


def _expand_table(table_name, table):
    """Expand every abstraction column in one table (section 6). Returns (expanded_table,
    generated_tables): plain columns pass through unchanged, abstraction columns are rewritten to
    their relational form, and any tables an abstraction generates are collected. Pure."""
    columns = {}
    constraints = dict(table.get("constraints", {}))
    generated = {}
    for column_name, column in table.get("columns", {}).items():
        kind = _abstraction_kind(column)
        if kind is None:
            columns[column_name] = column
            continue
        new_columns, new_constraints, new_tables = _EXPANDERS[kind](table_name, column_name, column)
        columns.update(new_columns)
        constraints.update(new_constraints)
        generated.update(new_tables)
    expanded = {**table, "columns": columns}
    if constraints:
        expanded["constraints"] = constraints
    return expanded, generated


def expand_schema(schema):
    """Expand every abstraction declaration in a bare Schema into ordinary tables, columns, and
    constraints (section 6). Pure schema -> schema: a schema with no abstractions is returned
    unchanged in shape; abstraction columns are rewritten, and the tables an abstraction generates
    are added alongside the owning table. Runs before diff and apply."""
    result = {}
    for table_name, table in schema.items():
        expanded, generated = _expand_table(table_name, table)
        result[table_name] = expanded
        result.update(generated)
    return result


def range_overlaps(column, lower, upper):
    """A WHERE condition (section 6.5): the range stored in `column` overlaps the query range
    [lower, upper]. Two ranges overlap when each starts at or before the other ends. Returns
    {sql, params}. Pure."""
    return {
        "sql": column + "_lower <= :" + column + "_ub AND " + column + "_upper >= :" + column + "_lb",
        "params": {column + "_ub": upper, column + "_lb": lower},
    }


def range_contains(column, point):
    """A WHERE condition (section 6.5): the range stored in `column` contains `point` — the point
    lies between the bounds. Returns {sql, params}. Pure."""
    return {
        "sql": column + "_lower <= :" + column + "_pt AND " + column + "_upper >= :" + column + "_pt",
        "params": {column + "_pt": point},
    }


def range_adjacent(column, lower, upper):
    """A WHERE condition (section 6.5): the range stored in `column` is adjacent to [lower, upper] —
    they touch at a bound, one's upper equal to the other's lower, without overlapping. Returns
    {sql, params}. Pure."""
    return {
        "sql": column + "_upper = :" + column + "_adj_l OR " + column + "_lower = :" + column + "_adj_u",
        "params": {column + "_adj_l": lower, column + "_adj_u": upper},
    }
