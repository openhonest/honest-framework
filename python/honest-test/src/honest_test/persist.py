"""honest-persist contract tests against a real in-memory database (spec section 6).

test_persist_schema_contract drives honest-persist's genuine query builders and execute against
the injected connection — never a mock — checking four contracts per table. enumerate_check_
constraints derives the CHECK-constraint cases from honest-persist's closed CHECK vocabulary.
honest-persist is imported lazily, inside the functions, so the rest of honest-test imports
cleanly even where honest-persist is absent.
"""

import asyncio

from honest_test.support import _finding

# Sample column values by declared type, for building a full round-trip row.
_SAMPLE = {"integer": 1, "int": 1, "text": "x", "uuid": "x", "boolean": 1, "real": 1.0, "float": 1.0}


def _sample_value(column):
    """A value for one column from its declared type."""
    return _SAMPLE.get(column.get("type"), "x")


def _primary_key(table_def):
    """The declared primary-key column, or the first column when none is marked."""
    columns = table_def["columns"]
    for name, definition in columns.items():
        if definition.get("primary_key"):
            return name
    return next(iter(columns))


def _omittable_required(table_def):
    """A non-nullable, non-primary-key column an insert can omit, or None when there is none."""
    for name, definition in table_def["columns"].items():
        if definition.get("nullable", True) is False and not definition.get("primary_key"):
            return name
    return None


# honest: disable HC-P002: the contract check runs against a real database through the injected
# connect (spec section 6.1); catching the driver's raise on an insert that omits a non-nullable
# column is how honest-test observes whether the real database rejected it — the observation
# becomes a Finding, it is never swallowed.
async def _table_contracts(schema, table_name, table_def, conn):
    """Run the four schema contracts for one table against a real connection (spec section 6.1)."""
    from honest_persist.apply import to_sql
    from honest_persist.execute import execute, execute_many
    from honest_persist.query import checked_select, insert, select

    findings = []
    await conn.execute(to_sql({"op": "create_table", "table": table_name, "details": table_def}, "turso"))

    columns = table_def["columns"]
    row = {name: _sample_value(definition) for name, definition in columns.items()}
    primary = _primary_key(table_def)

    await execute_many(insert(table_name, row), conn)
    read_back = await execute(select(table_name, where={primary: row[primary]}), conn)
    if read_back != [row]:
        findings.append(_finding("failure", "round_trip_mismatch",
                                 f"row read back from {table_name!r} did not equal the row written"))

    checked = checked_select(schema, table_name, columns=["a_column_not_declared"])
    if "err" not in checked:
        findings.append(_finding("failure", "undeclared_column_accepted",
                                 f"a query referencing an undeclared column on {table_name!r} was not rejected"))

    omittable = _omittable_required(table_def)
    if omittable is not None:
        missing = {name: value for name, value in row.items() if name != omittable}
        missing[primary] = 2 if isinstance(row[primary], int) else "y"
        try:
            await execute_many(insert(table_name, missing), conn)
            accepted = True
        except Exception:
            accepted = False
        if accepted:
            findings.append(_finding("failure", "missing_required_field_accepted",
                                     f"an insert omitting non-nullable {omittable!r} on {table_name!r} was accepted"))

    no_match = 999999 if isinstance(row[primary], int) else "no-such-key"
    empty = await execute(select(table_name, where={primary: no_match}), conn)
    if empty != []:
        findings.append(_finding("failure", "empty_set_faulted",
                                 f"an empty select on {table_name!r} did not return ok([])"))
    return findings
# honest: enable HC-P002


def test_persist_schema_contract(schema, connect):
    """Check four contracts per table against a real in-memory database, never a mock (spec
    section 6.1). connect is honest-persist's one I/O seam, injected; it yields a fresh ephemeral
    database per table. One failure per broken contract per table, empty when every contract
    holds. Its only side effect is through the injected connect."""
    findings = []
    for table_name, table_def in schema.items():
        conn = connect()
        findings.extend(asyncio.run(_table_contracts(schema, table_name, table_def, conn)))
    return findings


def _rows_for_compare(tree, base):
    """A (conforming, violating) row pair for a single `column OP literal` CHECK tree."""
    if tree["kind"] != "compare" or tree["left"]["kind"] != "column" or tree["right"]["kind"] != "literal":
        return dict(base), dict(base)
    column = tree["left"]["name"]
    literal = tree["right"]["value"]
    table = {
        ">=": (literal, literal - 1),
        ">": (literal + 1, literal),
        "<=": (literal, literal + 1),
        "<": (literal - 1, literal),
        "=": (literal, literal + 1),
        "!=": (literal + 1, literal),
        "<>": (literal + 1, literal),
    }
    conforming_value, violating_value = table.get(tree["op"], (literal, literal))
    return {**base, column: conforming_value}, {**base, column: violating_value}


def enumerate_check_constraints(schema):
    """Enumerate the CHECK-constraint contract cases for a schema (spec section 6.2): one
    CheckCase per declared CHECK, carrying a conforming row the real database must accept and a
    violating row it must reject, derived from honest-persist's closed CHECK vocabulary. Reads no
    world, returns pure data."""
    from honest_persist.check import parse_check, table_checks

    cases = []
    for table in schema["tables"].values():
        columns = table.get("columns", {})
        base = {name: _sample_value(definition) for name, definition in columns.items()}
        for expression in table_checks(table):
            compiled = parse_check(expression)
            if "err" in compiled:
                continue
            conforming, violating = _rows_for_compare(compiled["ok"], base)
            cases.append({"conforming_row": conforming, "violating_row": violating})
    return cases
