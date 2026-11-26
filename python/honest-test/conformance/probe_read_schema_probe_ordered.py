# scenario: read_schema_probe returns real probe outcomes in contract order
# inherits: hd=python/honest-test/honest-test.hd::read_schema_probe -> feature=specs/features/honest-test.feature::read_schema_probe returns real probe outcomes in contract order

import sqlite3
from contextlib import closing

from honest_test.persist_components import read_schema_probe

_ID = {"type": "INTEGER", "primary_key": True, "nullable": False}
_REQUIRED_TEXT = {"type": "TEXT", "nullable": False}
_NULLABLE_TEXT = {"type": "TEXT", "nullable": True}


def _connect():
    return sqlite3.connect(":memory:")


def _deny_select(action, _first, _second, _database, _trigger):
    return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK


def _restricted_connect():
    connection = sqlite3.connect(":memory:")
    connection.set_authorizer(_deny_select)
    return connection


def _bytes_text_connect():
    connection = sqlite3.connect(":memory:")
    connection.text_factory = bytes
    return connection



def probe_read_schema_probe_ordered():
    cases = (
        (
            _connect,
            {"columns": {"id": _ID, "email": _REQUIRED_TEXT, "name": _REQUIRED_TEXT}, "primary_key": ["id"]},
            ["round_trip_equal", "undeclared_column_rejected", "missing_required_field_rejected", "empty_rows"],
        ),
        (_connect, {"columns": {"id": _ID}, "primary_key": ["id"]},
         ["round_trip_equal", "undeclared_column_rejected", "empty_rows"]),
        (
            _connect,
            {"columns": {"label": _NULLABLE_TEXT, "id": _ID}, "primary_key": ["id"]},
            ["round_trip_equal", "undeclared_column_rejected", "empty_rows"],
        ),
        (
            _connect,
            {
                "columns": {
                    "account": _ID,
                    "region": {"type": "TEXT", "primary_key": True, "nullable": False},
                    "name": _REQUIRED_TEXT,
                    "label": _NULLABLE_TEXT,
                },
                "primary_key": ["account", "region"],
            },
            ["round_trip_equal", "undeclared_column_rejected", "missing_required_field_rejected", "empty_rows"],
        ),
        (
            _connect,
            {"columns": {"label": _NULLABLE_TEXT}, "primary_key": []},
            ["round_trip_equal", "undeclared_column_rejected", "empty_rows"],
        ),
        (
            _bytes_text_connect,
            {"columns": {"label": _NULLABLE_TEXT}, "primary_key": []},
            ["round_trip_mismatch", "undeclared_column_rejected", "empty_rows"],
        ),
        (_restricted_connect, {"columns": {"id": _ID, "email": _REQUIRED_TEXT}, "primary_key": ["id"]},
         ["round_trip_mismatch", "undeclared_column_rejected", "missing_required_field_rejected", "empty_set_faulted"]),
    )
    failures = []
    for connect, table, expected in cases:
        actual = read_schema_probe("widgets", table, connect)
        if actual != expected:
            failures.append(f"{connect.__name__}: got {actual!r}, expected {expected!r}")
    with closing(sqlite3.connect(":memory:")) as connection:
        statements = []
        connection.set_trace_callback(statements.append)
        table = {
            "columns": {
                "name": _REQUIRED_TEXT,
                "score": {"type": "REAL", "nullable": False},
                "payload": {"type": "BLOB", "nullable": True},
                "label": _NULLABLE_TEXT,
            },
            "primary_key": [],
        }
        outcomes = read_schema_probe("widgets", table, lambda: connection)
        expected = ["round_trip_equal", "undeclared_column_rejected", "missing_required_field_rejected", "empty_rows"]
        if outcomes != expected:
            failures.append(f"required field probe without any competing primary-key constraint: {outcomes!r}")
        inserts = [sql for sql in statements if sql.lstrip().upper().startswith("INSERT INTO ")]
        observed_columns = [
            [name.strip() for name in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
            for sql in inserts
        ]
        expected_columns = [["name", "score", "payload", "label"], ["score", "payload", "label"]]
        if observed_columns != expected_columns:
            failures.append(f"expected the real omission attempt to omit only name, got {observed_columns!r}")
        storage = connection.execute("SELECT typeof(score), typeof(payload) FROM widgets").fetchall()
        if storage != [("real", "blob")]:
            failures.append(f"the valid probe row must carry native REAL and BLOB values, got {storage!r}")

    with closing(sqlite3.connect(":memory:")) as connection:
        table = {"columns": {"id": _ID, "label": _NULLABLE_TEXT}, "primary_key": ["id"]}
        read_schema_probe("widgets", table, lambda: connection)
        key = connection.execute("SELECT name FROM pragma_table_info('widgets') WHERE pk > 0").fetchall()
        if key != [("id",)]:
            failures.append(f"table setup must install the declared single-column primary key, got {key!r}")

    for declared_name in ("no_such_column", "NO_SUCH_COLUMN"):
        table = {"columns": {declared_name: _NULLABLE_TEXT}, "primary_key": []}
        outcomes = read_schema_probe("widgets", table, _connect)
        expected = ["round_trip_equal", "undeclared_column_rejected", "empty_rows"]
        if outcomes != expected:
            failures.append(f"declared SQLite column {declared_name!r}: got {outcomes!r}, expected {expected!r}")

    return failures


def run():
    failures = probe_read_schema_probe_ordered()
    for failure in failures:
        print(f"FAIL read_schema_probe returns real probe outcomes in contract order: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
