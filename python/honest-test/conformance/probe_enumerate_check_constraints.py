# scenario: enumerate_check_constraints enumerates the CHECK-constraint contract cases
# inherits: hd=python/honest-test/honest-test.hd::enumerate_check_constraints -> feature=specs/features/honest-test.feature::enumerate_check_constraints enumerates the CHECK-constraint contract cases
"""honest-test conformance: enumerate_check_constraints.

enumerate_check_constraints(schema) -> list<CheckCase> produces, for each CHECK declared
on a table, one CheckCase carrying a conforming_row the real database must accept and a
violating_row it must reject, both derived from the closed, finite constraint vocabulary
(honest-test-architecture.md section 6.2). It reads no world and returns pure data; a real in-memory SQLite check confirms the generated boundary rows.

A pure extractor over a real honest-persist Schema (dict of table name to Table; a column
carries a CHECK in its "check" field — honest-persist types.py Column.check). This probe
builds a schema with exactly one CHECK and a schema with none, and asserts the cases.

The exact row values the closed constraint vocabulary picks are honest-test's to fix, so
this probe asserts the derivable contract: one case per CHECK, each a full row for the
table, the conforming row satisfying the constraint and the violating row breaking it.
No classes, no mocks.
"""

from contextlib import closing
import sqlite3

from honest_test import enumerate_check_constraints


_COLUMNS = ("id", "email", "age")

_ONE_CHECK_SCHEMA = {
    "users": {
        "columns": {
            "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
            "email": {"type": "TEXT", "nullable": False},
            "age": {"type": "INTEGER", "nullable": False, "check": "age >= 0"},
        },
        "primary_key": ["id"],
    },
}

_NO_CHECK_SCHEMA = {
    "items": {
        "columns": {
            "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
            "label": {"type": "TEXT", "nullable": False},
        },
        "primary_key": ["id"],
    },
}


def probe_enumerate_check_constraints():
    bad = []

    cases = enumerate_check_constraints(_ONE_CHECK_SCHEMA)
    if not isinstance(cases, list):
        bad.append(f"enumerate_check_constraints should return a list, got {cases!r}")
        return bad
    if len(cases) != 1:
        bad.append(f"one declared CHECK should yield exactly one CheckCase, got {len(cases)}: {cases!r}")

    for case in cases:
        if not isinstance(case, dict):
            bad.append(f"each CheckCase should be a dict, got {case!r}")
            continue
        conforming = case.get("conforming_row")
        violating = case.get("violating_row")
        if not isinstance(conforming, dict) or not isinstance(violating, dict):
            bad.append(f"a CheckCase carries conforming_row and violating_row dicts, got {case!r}")
            continue
        for column in _COLUMNS:
            if column not in conforming:
                bad.append(f"the conforming row should be a full row and include {column!r}, got {conforming!r}")
            if column not in violating:
                bad.append(f"the violating row should be a full row and include {column!r}, got {violating!r}")
        if "age" in conforming and not (isinstance(conforming["age"], int) and conforming["age"] >= 0):
            bad.append(f"the conforming row must satisfy 'age >= 0', got age={conforming.get('age')!r}")
        if "age" in violating and not (isinstance(violating["age"], int) and violating["age"] < 0):
            bad.append(f"the violating row must break 'age >= 0', got age={violating.get('age')!r}")

    minimum, maximum = -(2**63), 2**63 - 1
    boundaries = (
        (">=", minimum + 1), (">", maximum - 1), ("<=", maximum - 1),
        ("<", minimum + 1), ("==", maximum - 1), ("!=", maximum - 1),
    )
    for operator, bound in boundaries:
        expression = f"amount {operator} {bound}"
        sqlite_schema = {
            "limits": {
                "columns": {"amount": {"type": "INTEGER", "check": expression}},
                "primary_key": [],
            },
        }
        cases = enumerate_check_constraints(sqlite_schema)
        if len(cases) != 1:
            bad.append(f"{expression} must yield one case, got {cases!r}")
            continue
        case = cases[0]
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute(f"CREATE TABLE limits (amount INTEGER CONSTRAINT limit_check CHECK ({expression}))")
            try:
                connection.execute("INSERT INTO limits VALUES (?)", (case["conforming_row"]["amount"],))
            except (sqlite3.IntegrityError, OverflowError):
                bad.append(f"{expression} must accept the conforming row")
            try:
                connection.execute("INSERT INTO limits VALUES (?)", (case["violating_row"]["amount"],))
            except sqlite3.IntegrityError as error:
                if "CHECK constraint failed: limit_check" not in str(error):
                    bad.append(f"{expression} must reject the violating row through the CHECK, got {error}")
            except OverflowError:
                bad.append(f"{expression} must use a real SQLite integer in the violating row")
            else:
                bad.append(f"{expression} must reject the violating row")

    empty = enumerate_check_constraints(_NO_CHECK_SCHEMA)
    if empty != []:
        bad.append(f"a schema with no CHECK should yield no cases, got {empty!r}")

    return bad


def run():
    messages = probe_enumerate_check_constraints()
    for message in messages:
        print(f"FAIL HT-probe [enumerate_check_constraints]: {message}")
    print(f"enumerate_check_constraints: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
