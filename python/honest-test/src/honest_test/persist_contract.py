"""honest-persist contract tests (section 6): verify an adopter's schema and queries against a real
database, never a mock.

honest-persist's one I/O seam is the injected `connect` (honest-persist §8.1), so honest-test hands
it a real in-memory driver, applies the declared schema to a fresh ephemeral database, and drives the
genuine query builders and `execute` against it. A conforming row round-trips; an undeclared column is
caught pure by `checked_insert` before any SQL runs; a CHECK, NOT NULL, or type violation is caught by
the real database at the write. This module IS the write boundary: it turns the database's rejection
into a fault value, which is what a boundary is for.
"""

from honest_persist import apply, checked_insert, checked_select, diff, execute
from honest_type import err, fault, link, ok


@link(boundary=True)
async def verify_write(schema, table, row, connect, dialect) -> dict:
    """Round-trip one row against a real database (section 6.1). Returns ok(the rows read back) on a
    clean round-trip, or err(fault) when the schema is invalid, a column is undeclared, or the real
    database rejects the row. Applies the declared schema to a fresh connection, so each call runs
    against a clean ephemeral database (honest-persist §8.2)."""
    plan = diff({}, schema)
    if "err" in plan:
        return plan
    built = checked_insert(schema, table, row, dialect)
    if "err" in built:
        return built
    conn = connect()
    await apply(plan, schema, conn, dialect)
    try:
        await execute(built["ok"], conn)
    except Exception as exc:
        return err(fault("write_rejected", str(exc), "client", {"table": table}))
    return ok(await execute(checked_select(schema, table)["ok"], conn))
