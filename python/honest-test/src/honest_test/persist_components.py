"""The persistence-contract and component-isolation checks (spec sections 6, 7). The
persist check drives a real in-memory database through an injected connect; the
component checks read component records as data. honest-test takes no import dependency
on honest-persist or honest-page — the schema and components arrive as data and the
database and loader arrive as injected callables, so a one-way dependency is never
created.
"""

import re

from honest_test._util import _choose, _pick, _read_or

_finding = lambda kind, code, message, location: {"kind": kind, "code": code, "message": message, "location": location}

_CLASS_RE = re.compile(r'class\s*=\s*"([^"]*)"')
_DEFAULTS = {"INTEGER": 1, "TEXT": "value", "REAL": 1.0, "BLOB": b"x"}


def extract_css_classes(template):
    """Pull the CSS class names a component's rendered HTML references out of its template
    (section 7.1), so test_css_isolation can intersect one component's classes against
    another's."""
    out = set()
    for attribute in _CLASS_RE.findall(template):
        out.update(attribute.split())
    return out


def test_css_isolation(component_a, component_b):
    """Fault css_namespace_collision when two components share a CSS class name (section
    7.1): each component must namespace under its own BEM block."""
    shared = extract_css_classes(component_a["template"]) & extract_css_classes(component_b["template"])
    return _choose(
        len(shared) > 0,
        [_finding("failure", "css_namespace_collision", f"components {component_a['name']!r} and {component_b['name']!r} share CSS classes {sorted(shared)}", "")],
        [],
    )


def test_route_isolation(components):
    """Fault route_collision when two components define the same route path (section 7.2),
    one failure per collided path."""
    owners = {}
    for component in components:
        for route in component["routes"]:
            owners.setdefault(route["path"], []).append(component["name"])
    collided = filter(lambda item: len(item[1]) > 1, owners.items())
    return [_finding("failure", "route_collision", f"route path {path!r} is defined by components {names}", "") for path, names in collided]


def test_startup_isolation(components, load_component):
    """Fault startup_cascade when one component failing to load causes another to fail
    (section 7.3): when one component fails, every other must still load. The injected
    loader drives the genuine load; honest-test observes which loads then fail."""
    def _safe_load(component):
        try:  # honest: ignore HC-P002: the injected loader is a boundary plug driven here; its raise is observed as a failure value, the seam section 7.3 names
            load_component(component)
            return True
        except Exception:
            return False

    names = [component["name"] for component in components]
    isolation = {component["name"]: _safe_load(component) for component in reversed(components)}
    natural = [(component["name"], _safe_load(component)) for component in components]
    cascaded = filter(lambda pair: _read_or(isolation, pair[0], False) and not pair[1], natural)

    def _trigger_for(name):
        before = natural[:names.index(name)]
        failed_before = [earlier for earlier, ok in filter(lambda pair: not pair[1], before)]
        return _pick(len(failed_before) > 0, lambda: failed_before[0], lambda: "an earlier component")

    def _cascade_finding(pair):
        name = pair[0]
        trigger = _trigger_for(name)
        return _finding("failure", "startup_cascade", f"component {name!r} failed to load after {trigger!r} failed — the components are not independently loadable", "")

    return [_cascade_finding(pair) for pair in cascaded]


def enumerate_check_constraints(schema):
    """Enumerate the CHECK-constraint contract cases for a schema (section 6.2): for each
    CHECK declared on a table, one CheckCase carrying a conforming row the real database
    must accept and a violating row it must reject, both full rows."""
    def _check_values(expression):
        tokens = expression.split()
        operator = tokens[1]
        bound = int(tokens[2])
        table = {
            ">=": (bound, bound - 1),
            ">": (bound + 1, bound),
            "<=": (bound, bound + 1),
            "<": (bound - 1, bound),
            "==": (bound, bound + 1),
            "!=": (bound + 1, bound),
        }
        return _read_or(table, operator, (bound, bound))

    def _base_row(columns):
        return {name: _read_or(_DEFAULTS, column["type"], "value") for name, column in columns.items()}

    def _table_cases(table):
        columns = table["columns"]
        checked = filter(lambda item: "check" in item[1], columns.items())
        base = _base_row(columns)
        out = []
        for column_name, column in checked:
            conforming, violating = _check_values(column["check"])
            out.append({"conforming_row": {**base, column_name: conforming}, "violating_row": {**base, column_name: violating}})
        return out

    return [case for table in schema.values() for case in _table_cases(table)]


def test_persist_schema_contract(schema, connect):
    """Check each table's four persistence contracts against a real in-memory database,
    never a mock (section 6.1): round_trip_mismatch, undeclared_column_accepted,
    missing_required_field_accepted and empty_set_faulted. The only side effect is through
    the injected connect, a real driver."""
    def _row_value(column):
        return _read_or(_DEFAULTS, column["type"], "value")

    def _column_def(name, column):
        null_clause = _choose(_read_or(column, "nullable", True), "", " NOT NULL")
        return f"{name} {column['type']}{null_clause}"

    def _create_sql(table_name, table):
        column_defs = [_column_def(name, column) for name, column in table["columns"].items()]
        pk = table["primary_key"]
        pk_clause = _choose(len(pk) > 0, [f"PRIMARY KEY ({', '.join(pk)})"], [])
        return f"CREATE TABLE {table_name} ({', '.join(column_defs + pk_clause)})"

    def _round_trip(connection, table_name, columns):
        names = [name for name, _ in columns]
        values = [_row_value(column) for _, column in columns]
        placeholders = ", ".join(["?"] * len(values))
        try:  # honest: ignore HC-P002: the real database is driven at the injected connect boundary; a raised error is the contract failure this observes (section 6.1)
            connection.execute(f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})", values)
            read = connection.execute(f"SELECT {', '.join(names)} FROM {table_name}").fetchall()
            matches = len(read) == 1 and list(read[0]) == values
            return _choose(matches, [], [_finding("failure", "round_trip_mismatch", f"a row read back from {table_name!r} did not equal the row written", "")])
        except Exception:
            return [_finding("failure", "round_trip_mismatch", f"writing and reading a row of {table_name!r} faulted", "")]

    def _undeclared_column(connection, table_name):
        try:  # honest: ignore HC-P002: the real database is driven at the injected connect boundary; the raised operational error is the rejection this contract observes (section 6.1)
            connection.execute(f"SELECT no_such_column FROM {table_name}").fetchall()
            return [_finding("failure", "undeclared_column_accepted", f"a query referencing an undeclared column of {table_name!r} was not rejected", "")]
        except Exception:
            return []

    def _missing_required_probe(connection, table_name, columns, missing):
        present = list(filter(lambda item: item[0] != missing[0], columns))
        names = [name for name, _ in present]
        values = [_row_value(column) for _, column in present]
        placeholders = ", ".join(["?"] * len(values))
        try:  # honest: ignore HC-P002: the real database is driven at the injected connect boundary; the raised integrity error is the rejection this contract observes (section 6.1)
            connection.execute(f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})", values)
            return [_finding("failure", "missing_required_field_accepted", f"an insert omitting non-nullable column {missing[0]!r} of {table_name!r} was not rejected", "")]
        except Exception:
            return []

    def _missing_required(connection, table_name, columns):
        required = list(filter(lambda item: not _read_or(item[1], "nullable", True) and not _read_or(item[1], "primary_key", False), columns))
        return _pick(len(required) == 0, lambda: [], lambda: _missing_required_probe(connection, table_name, columns, required[0]))

    def _empty_set(connection, table_name):
        try:  # honest: ignore HC-P002: the real database is driven at the injected connect boundary; an unexpected raise is the fault this contract observes (section 6.1)
            rows = connection.execute(f"SELECT * FROM {table_name} WHERE 1 = 0").fetchall()
            return _choose(list(rows) == [], [], [_finding("failure", "empty_set_faulted", f"a select matching no rows of {table_name!r} did not return an empty list", "")])
        except Exception:
            return [_finding("failure", "empty_set_faulted", f"a select matching no rows of {table_name!r} returned a fault", "")]

    def _table_findings(item):
        table_name, table = item
        connection = connect()
        connection.execute(_create_sql(table_name, table))
        columns = list(table["columns"].items())
        return (
            _round_trip(connection, table_name, columns)
            + _undeclared_column(connection, table_name)
            + _missing_required(connection, table_name, columns)
            + _empty_set(connection, table_name)
        )

    return [found for item in schema.items() for found in _table_findings(item)]
