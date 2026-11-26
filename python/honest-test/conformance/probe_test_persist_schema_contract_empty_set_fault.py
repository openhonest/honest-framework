# scenario: test_persist_schema_contract reports a valid empty-set read fault
# inherits: hd=python/honest-test/honest-test.hd::test_persist_schema_contract -> feature=specs/features/honest-test.feature::test_persist_schema_contract reports a valid empty-set read fault

"""Prove that a real SQLite authorization error is an empty-set fault."""

import sqlite3

from honest_test import test_persist_schema_contract

_SCHEMA = {
    "users": {
        "columns": {
            "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
            "email": {"type": "TEXT", "nullable": False},
        },
        "primary_key": ["id"],
    },
}
_SQLITE_POLICY = {sqlite3.SQLITE_SELECT: sqlite3.SQLITE_DENY}
_EXPECTED = [{"kind": "failure", "code": "empty_set_faulted"}]


def _authorize(operation, _first, _second, _database, _trigger):
    return _SQLITE_POLICY.get(operation, sqlite3.SQLITE_OK)


def _connect():
    connection = sqlite3.connect(":memory:")
    connection.set_authorizer(_authorize)
    return connection


def probe_test_persist_schema_contract_empty_set_fault():
    """A rejected empty-set query reports one failure for the table."""
    findings = test_persist_schema_contract(_SCHEMA, _connect)
    empty_set_failures = [
        {"kind": finding["kind"], "code": finding["code"]}
        for finding in findings
        if finding["code"] == "empty_set_faulted"
    ]
    if empty_set_failures != _EXPECTED:
        return [f"got {empty_set_failures!r}, expected {_EXPECTED!r}"]
    return []


def run():
    failures = probe_test_persist_schema_contract_empty_set_fault()
    for failure in failures:
        print(f"FAIL test_persist_schema_contract empty-set fault: {failure}")
    if not failures:
        print("PASS test_persist_schema_contract empty-set fault")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
