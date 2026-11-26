# scenario: read_schema_probe propagates fixture setup failures
# inherits: hd=python/honest-test/honest-test.hd::read_schema_probe -> feature=specs/features/honest-test.feature::read_schema_probe propagates fixture setup failures

import sqlite3

from honest_test.persist_components import read_schema_probe

_TABLE = {
    "columns": {"id": {"type": "INTEGER", "primary_key": True, "nullable": False}},
    "primary_key": ["id"],
}


def _bad_open():
    return sqlite3.connect("file::memory:?mode=invalid", uri=True)


def _deny_create_table(action, _first, _second, _database, _trigger):
    return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE else sqlite3.SQLITE_OK


def _ddl_denied():
    connection = sqlite3.connect(":memory:")
    connection.set_authorizer(_deny_create_table)
    return connection


def probe_read_schema_probe_setup_failure():
    failures = []
    for connect in (_bad_open, _ddl_denied):
        try:
            read_schema_probe("widgets", _TABLE, connect)
        except sqlite3.OperationalError:
            continue
        except sqlite3.DatabaseError:
            if connect is _ddl_denied:
                continue
            failures.append(f"{connect.__name__}: connection setup raised the wrong SQLite error")
        else:
            failures.append(f"{connect.__name__}: expected the real SQLite setup error to propagate")
    return failures


def run():
    failures = probe_read_schema_probe_setup_failure()
    for failure in failures:
        print(f"FAIL read_schema_probe propagates fixture setup failures: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
