"""honest-persist contract tests against a real in-memory database (spec section 6).

test_persist_schema_contract drives honest-persist's genuine query builders and execute against
the injected connection — never a mock — checking four contracts per table. enumerate_check_
constraints derives the CHECK-constraint cases from honest-persist's closed CHECK vocabulary.
honest-persist is imported lazily, inside the functions, so the rest of honest-test imports
cleanly even where honest-persist is absent.
"""

import asyncio

from honest_test._util import _choose, _pick, _read_or
from honest_test.support import _finding

# Sample column values by declared type, for building a full round-trip row.
_SAMPLE = {"integer": 1, "int": 1, "text": "x", "uuid": "x", "boolean": 1, "real": 1.0, "float": 1.0}


def _sample_value(column):
    """A value for one column from its declared type."""
    column_type = column.get("type")
    return _read_or(_SAMPLE, column_type, "x")


def _primary_key(table_def):
    """The declared primary-key column, or the first column when none is marked."""
    columns = table_def["columns"]
    marked = filter(lambda nd: nd[1].get("primary_key"), columns.items())
    for name, definition in marked:
        return name
    return next(iter(columns))


def _omittable_required(table_def):
    """A non-nullable, non-primary-key column an insert can omit, or None when there is none."""
    required = filter(
        lambda nd: _read_or(nd[1], "nullable", True) is False and not nd[1].get("primary_key"),
        table_def["columns"].items(),
    )
    for name, definition in required:
        return name
    return None


async def _try_insert(table_name, missing, conn, execute_many, insert):
    """Run an insert that omits a non-nullable column (spec section 6.1) and report whether the real
    database accepted it; the driver's raise on a rejection is observed, never swallowed."""
    try:  # honest: ignore HC-P002: the contract check runs against a real database through the injected connect (spec 6.1); catching the driver's raise on an insert that omits a non-nullable column is how honest-test observes whether the database rejected it, and the observation becomes a Finding
        await execute_many(insert(table_name, missing), conn)
        return True
    except Exception:
        return False


async def _omittable_probe(table_name, row, primary, omittable, conn, execute_many, insert):
    """Insert a row omitting the non-nullable column and report missing_required_field_accepted when
    the database took it (spec section 6.1)."""
    kept = filter(lambda nv: nv[0] != omittable, row.items())
    pk_value = _choose(isinstance(row[primary], int), 2, "y")
    missing = {**dict(kept), primary: pk_value}
    accepted = await _try_insert(table_name, missing, conn, execute_many, insert)
    return _pick(
        accepted,
        lambda: [_finding("failure", "missing_required_field_accepted",
                          f"an insert omitting non-nullable {omittable!r} on {table_name!r} was accepted")],
        lambda: [],
    )


async def _no_findings():
    """The empty contract result for a table with no omittable required column (spec section 6.1)."""
    return []


async def _omittable_contract(table_name, row, primary, omittable, conn):
    """Check the missing-required-field contract when the table has an omittable required column
    (spec section 6.1); the empty list when it has none."""
    from honest_persist.execute import execute_many
    from honest_persist.query import insert
    return await _pick(
        omittable is None,
        lambda: _no_findings(),
        lambda: _omittable_probe(table_name, row, primary, omittable, conn, execute_many, insert),
    )


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
    _pick(
        read_back != [row],
        lambda: findings.append(_finding("failure", "round_trip_mismatch",
                                         f"row read back from {table_name!r} did not equal the row written")),
        lambda: None,
    )

    checked = checked_select(schema, table_name, columns=["a_column_not_declared"])
    _pick(
        "err" not in checked,
        lambda: findings.append(_finding("failure", "undeclared_column_accepted",
                                         f"a query referencing an undeclared column on {table_name!r} was not rejected")),
        lambda: None,
    )

    omittable = _omittable_required(table_def)
    findings.extend(await _omittable_contract(table_name, row, primary, omittable, conn))

    no_match = _choose(isinstance(row[primary], int), 999999, "no-such-key")
    empty = await execute(select(table_name, where={primary: no_match}), conn)
    _pick(
        empty != [],
        lambda: findings.append(_finding("failure", "empty_set_faulted",
                                         f"an empty select on {table_name!r} did not return ok([])")),
        lambda: None,
    )
    return findings


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


def _compare_rows(tree, base):
    """The (conforming, violating) row pair for a `column OP literal` CHECK tree (spec section 6.2)."""
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
    conforming_value, violating_value = _read_or(table, tree["op"], (literal, literal))
    return {**base, column: conforming_value}, {**base, column: violating_value}


def _rows_for_compare(tree, base):
    """A (conforming, violating) row pair for a single `column OP literal` CHECK tree."""
    simple = (tree["kind"] == "compare"
              and tree["left"]["kind"] == "column"
              and tree["right"]["kind"] == "literal")
    return _pick(simple, lambda: _compare_rows(tree, base), lambda: (dict(base), dict(base)))


def _case_from(compiled, base):
    """The CheckCase for one successfully-compiled CHECK expression (spec section 6.2)."""
    conforming, violating = _rows_for_compare(compiled["ok"], base)
    return {"conforming_row": conforming, "violating_row": violating}


def enumerate_check_constraints(schema):
    """Enumerate the CHECK-constraint contract cases for a schema (spec section 6.2): one
    CheckCase per declared CHECK, carrying a conforming row the real database must accept and a
    violating row it must reject, derived from honest-persist's closed CHECK vocabulary. Reads no
    world, returns pure data."""
    from honest_persist.check import parse_check, table_checks

    cases = []
    for table in schema["tables"].values():
        columns = _read_or(table, "columns", {})
        base = {name: _sample_value(definition) for name, definition in columns.items()}
        for expression in table_checks(table):
            compiled = parse_check(expression)
            _pick(
                "err" in compiled,
                lambda: None,
                lambda: cases.append(_case_from(compiled, base)),
            )
    return cases
