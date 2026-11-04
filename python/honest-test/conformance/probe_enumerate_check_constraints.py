"""Conformance fragment for the enumerate_check_constraints scenario (honest-test.feature).

Scenario: enumerate_check_constraints enumerates the CHECK-constraint contract cases for a schema.
  Then for each CHECK declared on a table it produces one CheckCase carrying a conforming row the
  real database must accept and a violating row it must reject, both derived from the closed
  CHECK-expression vocabulary, never supplied by hand.
  And it returns the list of cases for the contract runner to drive against the real database.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.enumerate_check_constraints and
returns a list of failure strings (empty when every case holds). No classes, no mocks.

The input schemas are honest-persist's real data shape (honest-persist/src/honest_persist, section
4.15 / section 6.2): a SchemaDefinition is {"tables": {name: table}, "views", "triggers",
"procedures"}; a table carries a `columns` map (each column dict may carry a `check` string) and a
`constraints` map (each check constraint is {"type": "check", "expression": <str>}). `table_checks`
in honest-persist reads exactly those two sources. The schemas below are plain dict data, so no
honest-persist import is needed to build them; the one import that must resolve is honest_test.

The exact conforming / violating row the implementation derives from the constraint vocabulary is
not fixed by the scenario, so this probe does not pin a literal row. It pins the two things the
scenario does fix: the count (one CheckCase per declared CHECK, none when a table declares no CHECK)
and the structural property on a constraint we can reason about (`<col> >= 0`): the conforming row
satisfies it and the violating row breaks it.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import enumerate_check_constraints

# A schema with exactly one column-level CHECK: `age >= 0` on person.age.
_SCHEMA_COLUMN_CHECK = {
    "tables": {
        "person": {
            "columns": {
                "name": {"type": "text"},
                "age": {"type": "integer", "check": "age >= 0"},
            },
            "constraints": {},
        },
    },
    "views": {},
    "triggers": {},
    "procedures": {},
}

# A schema with exactly one table-level CHECK constraint: `balance >= 0` on account.
_SCHEMA_TABLE_CHECK = {
    "tables": {
        "account": {
            "columns": {
                "owner": {"type": "text"},
                "balance": {"type": "integer"},
            },
            "constraints": {
                "balance_nonneg": {"type": "check", "expression": "balance >= 0"},
            },
        },
    },
    "views": {},
    "triggers": {},
    "procedures": {},
}

# A schema whose one table declares NO CHECK: the explicit absence case.
_SCHEMA_NO_CHECK = {
    "tables": {
        "log": {
            "columns": {
                "id": {"type": "integer"},
                "message": {"type": "text"},
            },
            "constraints": {},
        },
    },
    "views": {},
    "triggers": {},
    "procedures": {},
}

_CASES = [
    # One column CHECK `age >= 0` -> exactly one CheckCase whose rows obey/break `age >= 0`.
    {
        "schema": _SCHEMA_COLUMN_CHECK,
        "expect_count": 1,
        "column": "age",
        "floor": 0,
    },
    # One table-level CHECK `balance >= 0` -> exactly one CheckCase on `balance`.
    {
        "schema": _SCHEMA_TABLE_CHECK,
        "expect_count": 1,
        "column": "balance",
        "floor": 0,
    },
    # No CHECK declared -> no CheckCase. The explicit absence row.
    {
        "schema": _SCHEMA_NO_CHECK,
        "expect_count": 0,
        "column": None,
        "floor": None,
    },
]


def _satisfies_floor(row, column, floor):
    """True when `row` carries `column` as a number that is >= `floor`."""
    if column not in row:
        return False
    value = row[column]
    return isinstance(value, (int, float)) and value >= floor


def probe_enumerate_check_constraints():
    """enumerate_check_constraints yields one CheckCase per declared CHECK, each carrying a conforming row that satisfies the constraint and a violating row that breaks it, and none when a table declares no CHECK."""
    bad = []
    for case in _CASES:
        got = enumerate_check_constraints(case["schema"])
        if len(got) != case["expect_count"]:
            bad.append(
                f"enumerate_check_constraints(<schema>) produced {len(got)} CheckCase(s), "
                f"expected {case['expect_count']}"
            )
            continue
        if case["expect_count"] == 0:
            continue
        column = case["column"]
        floor = case["floor"]
        for check_case in got:
            conforming = check_case["conforming_row"]
            violating = check_case["violating_row"]
            if not _satisfies_floor(conforming, column, floor):
                bad.append(
                    f"enumerate_check_constraints(<schema>) conforming_row {conforming} "
                    f"does not satisfy `{column} >= {floor}`"
                )
            if _satisfies_floor(violating, column, floor):
                bad.append(
                    f"enumerate_check_constraints(<schema>) violating_row {violating} "
                    f"does not break `{column} >= {floor}`"
                )
    return bad


def run():
    bad = probe_enumerate_check_constraints()
    for line in bad:
        print(line)
    print(f"probe_enumerate_check_constraints: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
