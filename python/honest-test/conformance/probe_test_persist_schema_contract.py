"""honest-test conformance: test_persist_schema_contract.

test_persist_schema_contract(schema, connect) -> list<Finding> checks, for every table in
a declared schema, four contracts against a real in-memory database (never a mock) and
returns a failure for each that breaks: round_trip_mismatch, undeclared_column_accepted,
missing_required_field_accepted, and empty_set_faulted
(honest-test-architecture.md section 6.1).

connect is honest-persist's one I/O seam injected, returning a fresh ephemeral in-memory
database recreated per table; the only side effect is through that injected real driver.
This probe injects a real sqlite3 ":memory:" connection factory — a genuine database, not
a stand-in — and a well-formed schema (honest-persist types.py Schema shape: a dict of
table name to Table whose columns carry type, nullability and CHECK).

With a correct honest-persist driving a real database all four contracts hold, so a
well-formed schema returns no findings; forcing a contract to break would require a
database that silently accepts a missing required field or mangles a round trip — a
non-enforcing fake — which section 6 forbids. So the probe asserts the clean path and
guards the shape and code of any finding against the closed persist code set. No classes,
no mocks; a Finding is recognized by its own shape — a dict carrying a "code" and a "kind".
"""

import sqlite3

from honest_test import test_persist_schema_contract


_PERSIST_CODES = {
    "round_trip_mismatch",
    "undeclared_column_accepted",
    "missing_required_field_accepted",
    "empty_set_faulted",
}

_SCHEMA = {
    "users": {
        "columns": {
            "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
            "email": {"type": "TEXT", "nullable": False},
            "name": {"type": "TEXT", "nullable": True},
        },
        "primary_key": ["id"],
    },
}


def _is_finding(value):
    return isinstance(value, dict) and "code" in value and "kind" in value


def _connect():
    """A fresh real in-memory database per call, honest-persist's injected I/O seam."""
    return sqlite3.connect(":memory:")


def probe_test_persist_schema_contract():
    bad = []

    findings = test_persist_schema_contract(_SCHEMA, _connect)
    if not isinstance(findings, list):
        bad.append(f"test_persist_schema_contract should return a list, got {findings!r}")
        return bad

    # A well-formed schema against a correct honest-persist and a real database holds every
    # contract, so there is nothing to report.
    if findings != []:
        bad.append(f"a well-formed schema should hold every contract and yield no findings, got {findings!r}")

    # Shape guard: any finding this check ever emits is a failure drawn from the closed set.
    for finding in findings:
        if not _is_finding(finding):
            bad.append(f"each result should be a Finding carrying a code and a kind, got {finding!r}")
            continue
        if finding.get("kind") != "failure":
            bad.append(f"a persist contract breach is a failure, got kind {finding.get('kind')!r}")
        if finding.get("code") not in _PERSIST_CODES:
            bad.append(f"the code should be one of {_PERSIST_CODES}, got {finding.get('code')!r}")

    return bad


def run():
    messages = probe_test_persist_schema_contract()
    for message in messages:
        print(f"FAIL HT-probe [test_persist_schema_contract]: {message}")
    print(f"test_persist_schema_contract: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
