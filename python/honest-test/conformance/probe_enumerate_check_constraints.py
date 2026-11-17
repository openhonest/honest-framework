"""honest-test conformance: enumerate_check_constraints.

enumerate_check_constraints(schema) -> list<CheckCase> produces, for each CHECK declared
on a table, one CheckCase carrying a conforming_row the real database must accept and a
violating_row it must reject, both derived from the closed, finite constraint vocabulary
(honest-test-architecture.md section 6.2). It reads no world and returns pure data; the
running against the database is test_persist_schema_contract's injected connect, not here.

A pure extractor over a real honest-persist Schema (dict of table name to Table; a column
carries a CHECK in its "check" field — honest-persist types.py Column.check). This probe
builds a schema with exactly one CHECK and a schema with none, and asserts the cases.

The exact row values the closed constraint vocabulary picks are honest-test's to fix, so
this probe asserts the derivable contract: one case per CHECK, each a full row for the
table, the conforming row satisfying the constraint and the violating row breaking it.
No classes, no mocks.
"""

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
