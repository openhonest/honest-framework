"""The abstraction layer (section 6): high-level type declarations to ordinary relational structure.

The application declares intent — an enum, a hierarchy, an array, a range — and honest-persist
generates the tables, columns, and constraints that realize it. The whole expansion is one pure
function, `expand_schema`, run before a schema is diffed or applied. Nothing downstream sees an
abstraction: diff, apply, and inspect operate on the relational expansion, subject to exactly the
same verification as any hand-written schema. A column's abstraction is recognized by its declared
`type` and dispatched, by dict lookup, to the expander that rewrites it. This module starts with
ranges (section 6.5); each further abstraction adds an expander to the same table.
"""

from honest_persist.query import delete, insert, update


def _expand_range(table_name, table, column_name, column):
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


def _array_table(table, column):
    """The junction table name for an array column (section 6.4). Pure."""
    return "_hp_array_" + table + "_" + column


def _map_table(table, column):
    """The junction table name for a map column (section 6.4). Pure."""
    return "_hp_map_" + table + "_" + column


def _owner_type(table):
    """The base table's primary-key type, for a junction's owner reference (section 6.4); integer
    (the implicit rowid) when no primary key is declared. Pure."""
    columns = table.get("columns", {})
    for column in columns.values():
        if column.get("primary_key"):
            return column.get("type", "integer")
    for name in table.get("primary_key", []):
        if name in columns:
            return columns[name].get("type", "integer")
    return "integer"


def _expand_array(table_name, table, column_name, column):
    """An array column (section 6.4) to a junction table of (owner_id, ordinal, value); the base
    column is removed. Returns (columns, constraints, generated_tables). Pure."""
    junction = {"columns": {
        "owner_id": {"type": _owner_type(table), "nullable": False},
        "ordinal": {"type": "integer", "nullable": False},
        "value": {"type": column.get("element_type", "text"), "nullable": False},
    }}
    return {}, {}, {_array_table(table_name, column_name): junction}


def _expand_map(table_name, table, column_name, column):
    """A map column (section 6.4) to a junction table of (owner_id, key, value); the base column is
    removed. Returns (columns, constraints, generated_tables). Pure."""
    junction = {"columns": {
        "owner_id": {"type": _owner_type(table), "nullable": False},
        "key": {"type": column.get("key_type", "text"), "nullable": False},
        "value": {"type": column.get("value_type", "text"), "nullable": False},
    }}
    return {}, {}, {_map_table(table_name, column_name): junction}


def _closure_table(table):
    """The closure table name for a hierarchy on `table` (section 6.3). Pure."""
    return "_hp_closure_" + table


def _expand_hierarchy(table_name, table, column_name, column):
    """A hierarchy column (section 6.3) to a nullable self-referential parent column plus a closure
    table of (ancestor, descendant, depth). The node-id type is the base table's primary-key type.
    Returns (columns, constraints, generated_tables). Pure."""
    node_type = _owner_type(table)
    parent = {"type": node_type, "nullable": True}
    closure = {"columns": {
        "ancestor": {"type": node_type, "nullable": False},
        "descendant": {"type": node_type, "nullable": False},
        "depth": {"type": "integer", "nullable": False},
    }}
    return {column_name: parent}, {}, {_closure_table(table_name): closure}


# Each abstraction is recognized by the column's declared `type` and rewritten by its expander
# (section 6). Expanders return (columns, constraints, generated_tables).
_EXPANDERS = {
    "range": _expand_range,
    "array": _expand_array,
    "map": _expand_map,
    "hierarchy": _expand_hierarchy,
}


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
        new_columns, new_constraints, new_tables = _EXPANDERS[kind](table_name, table, column_name, column)
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


def array_append(table, column, owner_id, ordinal, value):
    """Append an element at `ordinal` to an array column (section 6.4): an INSERT into the junction
    table. Pure query builder."""
    return insert(_array_table(table, column), {"owner_id": owner_id, "ordinal": ordinal, "value": value})


def array_set(table, column, owner_id, ordinal, value):
    """Set the element at `ordinal` of an array column (section 6.4): an UPDATE of the junction row.
    Pure query builder."""
    return update(_array_table(table, column), {"value": value}, {"owner_id": owner_id, "ordinal": ordinal})


def array_remove(table, column, owner_id, ordinal):
    """Remove the element at `ordinal` of an array column (section 6.4): a DELETE of the junction row.
    Pair with array_reindex to close the gap. Pure query builder."""
    return delete(_array_table(table, column), {"owner_id": owner_id, "ordinal": ordinal})


def array_reindex(table, column, owner_id, removed_ordinal):
    """Close the gap a removal leaves in an array column (section 6.4): decrement the ordinals above
    the removed position. Pure query builder."""
    junction = _array_table(table, column)
    return {
        "sql": "UPDATE " + junction + " SET ordinal = ordinal - 1 WHERE owner_id = :owner_id AND ordinal > :removed",
        "params": {"owner_id": owner_id, "removed": removed_ordinal},
    }


def map_put(table, column, owner_id, key, value):
    """Put a key/value entry into a map column (section 6.4): an INSERT into the junction table. Pure
    query builder."""
    return insert(_map_table(table, column), {"owner_id": owner_id, "key": key, "value": value})


def map_remove(table, column, owner_id, key):
    """Remove a key from a map column (section 6.4): a DELETE of the junction row. Pure query
    builder."""
    return delete(_map_table(table, column), {"owner_id": owner_id, "key": key})


def closure_insert(table, node, parent):
    """Insert a node under `parent` into a hierarchy's closure (section 6.3): the node's self-pair at
    depth 0, plus a pair from every ancestor of the parent. A root (parent None) gets only its
    self-pair. Pure query builder."""
    closure = _closure_table(table)
    return {
        "sql": (
            "INSERT INTO " + closure + " (ancestor, descendant, depth) "
            "SELECT ancestor, :node, depth + 1 FROM " + closure + " WHERE descendant = :parent "
            "UNION ALL SELECT :node, :node, 0"
        ),
        "params": {"node": node, "parent": parent},
    }


def closure_descendants(table, node):
    """The descendants of a node, itself included (section 6.3): one read of the closure. Pure query
    builder."""
    closure = _closure_table(table)
    return {"sql": "SELECT descendant FROM " + closure + " WHERE ancestor = :node", "params": {"node": node}}


def closure_ancestors(table, node):
    """The ancestors of a node, itself included (section 6.3): one read of the closure. Pure query
    builder."""
    closure = _closure_table(table)
    return {"sql": "SELECT ancestor FROM " + closure + " WHERE descendant = :node", "params": {"node": node}}


def closure_delete(table, node):
    """Remove a node and its whole subtree from the closure (section 6.3). Pure query builder."""
    closure = _closure_table(table)
    return {
        "sql": (
            "DELETE FROM " + closure + " WHERE descendant IN "
            "(SELECT descendant FROM " + closure + " WHERE ancestor = :node)"
        ),
        "params": {"node": node},
    }


def closure_move(table, node, new_parent):
    """Relocate a subtree under `new_parent` (section 6.3), as two steps run in order: detach the
    subtree's cross-links to its old ancestors (keeping the links inside the subtree), then reconnect
    it under every ancestor of the new parent. Returns the two query builders. Pure."""
    closure = _closure_table(table)
    detach = {
        "sql": (
            "DELETE FROM " + closure + " WHERE descendant IN "
            "(SELECT descendant FROM " + closure + " WHERE ancestor = :node) "
            "AND ancestor NOT IN (SELECT descendant FROM " + closure + " WHERE ancestor = :node)"
        ),
        "params": {"node": node},
    }
    reconnect = {
        "sql": (
            "INSERT INTO " + closure + " (ancestor, descendant, depth) "
            "SELECT super.ancestor, sub.descendant, super.depth + sub.depth + 1 "
            "FROM " + closure + " super CROSS JOIN " + closure + " sub "
            "WHERE super.descendant = :new_parent AND sub.ancestor = :node"
        ),
        "params": {"node": node, "new_parent": new_parent},
    }
    return [detach, reconnect]
