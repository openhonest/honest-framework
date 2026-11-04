"""Conformance fragment for the test_persist_schema_contract scenario (honest-test.feature).

Scenario: test_persist_schema_contract checks four contracts per table against a real
  in-memory database.
  Then connect is honest-persist's one I/O seam, injected: it returns a fresh ephemeral
  in-memory database recreated per table so nothing leaks, and honest-test applies the
  declared schema and drives the genuine query builders and execute against it, never a
  mock. For every table it returns round_trip_mismatch, undeclared_column_accepted,
  missing_required_field_accepted or empty_set_faulted as the matching contract breaks, one
  failure per broken contract per table, empty when every table's contract holds.

Cases are data; one pure probe feeds them to the real honest_test.test_persist_schema_contract
and returns a list of failure strings (empty when every case holds). No mocks: the injected
connect yields honest-persist's genuine in-memory pyturso connection (the project's own
conformance adapter), so the database under test is real exactly as the note demands.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

import importlib.util
from pathlib import Path

from honest_test import test_persist_schema_contract

# ---------------------------------------------------------------------------
# A real in-memory database, not a mock. honest-persist does not bundle a
# connect; the host injects one. honest-persist's own conformance suite ships a
# genuine pyturso `:memory:` adapter (TursoConn) that speaks the module's
# duck-typed boundary: `await conn.execute(sql, params) -> {rows, rowcount}`.
# The probe reuses that real adapter rather than writing its own, so the driver
# is honest-persist's own and the connection is a real database.
# ---------------------------------------------------------------------------
_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "honest-persist"
    / "conformance"
    / "turso_fixture.py"
)
_spec = importlib.util.spec_from_file_location("hp_turso_fixture", _FIXTURE)
_turso_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_turso_fixture)


def _connect(*_args, **_kwargs):
    """A fresh ephemeral in-memory database, recreated on every call so nothing leaks between
    tables (the note's seam). Tolerant of the calling convention because the .hd fixes only
    `connect: Callable`, not whether it is awaited or passed a selector (a gap, see report)."""
    return _turso_fixture.turso_connection()


# ---------------------------------------------------------------------------
# The schema. honest-persist's REAL shape is `dict[table_name, Table]` with
# `Table = {"columns": {name: Column}}` (honest-persist/src/honest_persist/
# types.py). NOTE the honest-persist .hd declares `Schema = {tables: list<any>}`,
# which does not match the real code; the probe uses the real dict shape and the
# report flags the .hd mismatch as a gap.
# ---------------------------------------------------------------------------
_CLEAN_SCHEMA = {
    "widget": {
        "columns": {
            "id": {"type": "integer", "primary_key": True, "nullable": False},
            "name": {"type": "text", "nullable": False},
        },
    },
}

_CASES = [
    # The clean path: a table that honestly round-trips, rejects an undeclared column at
    # build time, rejects an insert missing a non-nullable column, and returns ok([]) on an
    # empty select. Every one of the four contracts holds against a correct honest-persist and
    # a real in-memory database, so the check returns the empty list.
    {
        "schema": _CLEAN_SCHEMA,
        "connect": _connect,
        "expect": [],
    },
]


def probe_test_persist_schema_contract():
    """test_persist_schema_contract returns no findings when every table's four contracts hold against a real in-memory database."""
    bad = []
    for case in _CASES:
        got = test_persist_schema_contract(case["schema"], case["connect"])
        if got != case["expect"]:
            bad.append(
                f"test_persist_schema_contract({case['schema']}, <real in-memory connect>) "
                f"-> {got}, expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_test_persist_schema_contract()
    for line in bad:
        print(line)
    print(f"probe_test_persist_schema_contract: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
