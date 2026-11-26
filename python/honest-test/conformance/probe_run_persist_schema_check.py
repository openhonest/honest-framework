# scenario: run_persist_schema_check collects ordered findings from fresh databases
# inherits: hd=python/honest-test/honest-test.hd::run_persist_schema_check -> feature=specs/features/honest-test.feature::run_persist_schema_check collects ordered findings from fresh databases

import sqlite3

from honest_test.persist_components import run_persist_schema_check

_TABLE = {
    "columns": {
        "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
        "email": {"type": "TEXT", "nullable": False},
    },
    "primary_key": ["id"],
}


def _deny_select(action, _first, _second, _database, _trigger):
    return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK


def probe_run_persist_schema_check():
    connections = []

    def connect():
        connection = sqlite3.connect(":memory:")
        connection.set_authorizer(_deny_select)
        connections.append(connection)
        return connection

    try:
        findings = run_persist_schema_check({"zebra": _TABLE, "ant": _TABLE}, connect)
    finally:
        for connection in connections:
            connection.close()
    if len(connections) != 2 or connections[0] is connections[1]:
        return ["each schema table must receive one fresh connection"]
    actual = [(item["kind"], item["code"]) for item in findings]
    expected = [
        ("failure", "round_trip_mismatch"), ("failure", "empty_set_faulted"),
        ("failure", "round_trip_mismatch"), ("failure", "empty_set_faulted"),
    ]
    if actual != expected:
        return [f"got {actual!r}, expected {expected!r}"]
    names = ("zebra", "zebra", "ant", "ant")
    if not all(name in item["message"] for name, item in zip(names, findings)):
        return [f"findings did not follow declaration order: {findings!r}"]
    return []


def run():
    failures = probe_run_persist_schema_check()
    for failure in failures:
        print(f"FAIL run_persist_schema_check collects ordered findings from fresh databases: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
