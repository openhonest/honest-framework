"""Mock data (section 8.9): the boundary's stand-in for real reads.

honest-persist owns the data boundary, so made-up data lives here too — the place real rows
are read from is the place fake rows come from. `mock_data_states` is a pure function: a
schema in, a list of small `{table: [row]}` datasets out — the same shape `run_action` and
`evaluate_guard` (guards.py / evaluate.py) take. honest-test (§5.4/§5.6) runs guards and
actions over each.

The datasets are tiny on purpose (the small-scope hypothesis): for each table it produces
every population of 0..max_rows rows, where each row's column values are drawn from that
column's declared set of allowed values; a column with no finite set (an id, an actor) draws
from a small fixed pool the caller supplies. Because the values and the row count are capped,
the list of datasets is finite and the caller can run over all of it.
"""

from itertools import combinations, product

from honest_persist.schema import _normalize


def _column_values(column_name, column, pools):
    """The candidate values for one column: its declared set, booleans, or a supplied pool
    (by column name, by type, or the '_default' fallback)."""
    if "literal_values" in column:
        return list(column["literal_values"])
    if column.get("type") == "boolean":
        return [True, False]
    if column_name in pools:
        return list(pools[column_name])
    return list(pools.get(column.get("type", ""), pools.get("_default", [])))


def _distinct_rows(columns, pools):
    """Every distinct row the table's columns can form (each combination of column values).
    Empty if any column has no candidate values — that table then has only the empty population."""
    names = list(columns)
    value_lists = [_column_values(name, columns[name], pools) for name in names]
    if not names or any(not values for values in value_lists):
        return []
    return [dict(zip(names, choice)) for choice in product(*value_lists)]


def _populations(rows, max_rows):
    """Every population of 0..max_rows distinct rows."""
    populations = [[]]
    for size in range(1, max_rows + 1):
        populations.extend([list(combo) for combo in combinations(rows, size)])
    return populations


def mock_data_states(schema, max_rows=2, pools=None):
    """Small made-up datasets for a schema (section 8.9). Pure. Returns a list of
    `{table: [row]}` states: for each table, every population of 0..max_rows rows whose column
    values come from the column's declared set (or a supplied pool). `pools` maps an
    open-ended column's name or type (or '_default') to its small value pool. Accepts a bare
    Schema or a SchemaDefinition."""
    tables = _normalize(schema)["tables"]
    pools = pools or {}
    per_table = {
        table: _populations(_distinct_rows(definition.get("columns", {}), pools), max_rows)
        for table, definition in tables.items()
    }
    names = sorted(per_table)
    if not names:
        return [{}]
    return [
        {name: combo[index] for index, name in enumerate(names)}
        for combo in product(*(per_table[name] for name in names))
    ]
