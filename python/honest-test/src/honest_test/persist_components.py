"""The persistence-contract and component-isolation checks (spec sections 6, 7). The
persist check drives a real in-memory database through an injected connect; the
component checks read component records as data. honest-test takes no import dependency
on honest-persist or honest-page — the schema and components arrive as data and the
database and loader arrive as injected callables, so a one-way dependency is never
created.
"""

import re

from honest_test._util import _choose, _read_or

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


# inherits: hd=python/honest-test/honest-test.hd::read_component_startup -> feature=specs/features/honest-test.feature::read_component_startup propagates a non-Exception BaseException -> test=python/honest-test/conformance/probe_read_component_startup_base_exception.py::probe_read_component_startup_base_exception
# inherits: hd=python/honest-test/honest-test.hd::read_component_startup -> feature=specs/features/honest-test.feature::read_component_startup records whether the loader returned -> test=python/honest-test/conformance/probe_read_component_startup_observed.py::probe_read_component_startup_observed
# hd: read_component_startup
def read_component_startup(load_component, component):
    """Record whether the supplied loader returned for the named component."""
    name = component["name"]
    try:
        load_component(component)
        loaded = True
    except Exception:
        loaded = False
    return {"name": name, "loaded": loaded}


# inherits: hd=python/honest-test/honest-test.hd::startup_cascade_findings -> feature=specs/features/honest-test.feature::startup_cascade_findings reports forward failures that passed in reverse -> test=python/honest-test/conformance/probe_startup_cascade_findings.py::probe_startup_cascade_findings
# hd: startup_cascade_findings
def startup_cascade_findings(names, reverse, forward):
    """Report forward failures of components that loaded in reverse order."""
    cascaded = filter(
        lambda observation: _read_or(reverse, observation["name"], False) and not observation["loaded"],
        forward,
    )
    findings = []
    for observation in cascaded:
        name = observation["name"]
        earlier = forward[:names.index(name)]
        failed = filter(lambda result: not result["loaded"], earlier)
        trigger = next((result["name"] for result in failed), "an earlier component")
        findings.append(_finding(
            "failure", "startup_cascade",
            f"component {name!r} failed to load after {trigger!r} failed — the components are not independently loadable", "",
        ))
    return findings


# inherits: hd=python/honest-test/honest-test.hd::run_startup_isolation_check -> feature=specs/features/honest-test.feature::run_startup_isolation_check loads components in reverse then forward order -> test=python/honest-test/conformance/probe_run_startup_isolation_check.py::probe_run_startup_isolation_check
# hd: run_startup_isolation_check
def run_startup_isolation_check(components, load_component):
    """Observe component startup in reverse and forward input order."""
    names = [component["name"] for component in components]
    reverse = {
        observation["name"]: observation["loaded"]
        for observation in (read_component_startup(load_component, component) for component in reversed(components))
    }
    forward = [read_component_startup(load_component, component) for component in components]
    return startup_cascade_findings(names, reverse, forward)


# inherits: hd=python/honest-test/honest-test.hd::test_startup_isolation -> feature=specs/features/honest-test.feature::test_startup_isolation checks that components are independently loadable -> test=python/honest-test/conformance/probe_test_startup_isolation.py::probe_test_startup_isolation
# hd: test_startup_isolation
def test_startup_isolation(components, load_component):
    """Return the startup isolation findings for the supplied components."""
    return run_startup_isolation_check(components, load_component)


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


# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets empty_rows -> test=python/honest-test/conformance/probe_schema_probe_findings_empty_rows.py::probe_schema_probe_findings_empty_rows
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets empty_set_faulted -> test=python/honest-test/conformance/probe_schema_probe_findings_empty_set_faulted.py::probe_schema_probe_findings_empty_set_faulted
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets missing_required_field_accepted -> test=python/honest-test/conformance/probe_schema_probe_findings_missing_required_field_accepted.py::probe_schema_probe_findings_missing_required_field_accepted
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets missing_required_field_rejected -> test=python/honest-test/conformance/probe_schema_probe_findings_missing_required_field_rejected.py::probe_schema_probe_findings_missing_required_field_rejected
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets round_trip_equal -> test=python/honest-test/conformance/probe_schema_probe_findings_round_trip_equal.py::probe_schema_probe_findings_round_trip_equal
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets round_trip_mismatch -> test=python/honest-test/conformance/probe_schema_probe_findings_round_trip_mismatch.py::probe_schema_probe_findings_round_trip_mismatch
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets undeclared_column_accepted -> test=python/honest-test/conformance/probe_schema_probe_findings_undeclared_column_accepted.py::probe_schema_probe_findings_undeclared_column_accepted
# inherits: hd=python/honest-test/honest-test.hd::schema_probe_findings -> feature=specs/features/honest-test.feature::schema_probe_findings interprets undeclared_column_rejected -> test=python/honest-test/conformance/probe_schema_probe_findings_undeclared_column_rejected.py::probe_schema_probe_findings_undeclared_column_rejected
# hd: schema_probe_findings
def schema_probe_findings(table, outcome):
    """Translate a completed probe observation into the declared findings."""
    messages = {
        "round_trip_equal": (),
        "undeclared_column_rejected": (),
        "missing_required_field_rejected": (),
        "empty_rows": (),
        "round_trip_mismatch": (f"the round trip for table {table!r} did not read back the row written",),
        "undeclared_column_accepted": (f"a query referencing an undeclared column of table {table!r} was not rejected",),
        "missing_required_field_accepted": (f"an insert omitting a non-nullable column of table {table!r} was not rejected",),
        "empty_set_faulted": (f"a select matching no rows of table {table!r} did not return an empty list",),
    }
    return [_finding("failure", outcome, message, "") for message in messages[outcome]]

# inherits: hd=python/honest-test/honest-test.hd::read_schema_probe -> feature=specs/features/honest-test.feature::read_schema_probe returns real probe outcomes in contract order -> test=python/honest-test/conformance/probe_read_schema_probe_ordered.py::probe_read_schema_probe_ordered
# inherits: hd=python/honest-test/honest-test.hd::read_schema_probe -> feature=specs/features/honest-test.feature::read_schema_probe propagates fixture setup failures -> test=python/honest-test/conformance/probe_read_schema_probe_setup_failure.py::probe_read_schema_probe_setup_failure
# hd: read_schema_probe
def read_schema_probe(table_name, table, connect):
    """Open and probe a fresh real database, returning its ordered observations."""
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

    outcomes = []
    connection = connect()
    connection.execute(_create_sql(table_name, table))
    columns = list(table["columns"].items())
    names = [name for name, _ in columns]
    values = [_row_value(column) for _, column in columns]
    placeholders = ", ".join(["?"] * len(values))

    try:
        connection.execute(f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})", values)
        read = connection.execute(f"SELECT {', '.join(names)} FROM {table_name}").fetchall()
        equal = len(read) == 1 and list(read[0]) == values
    except Exception:
        equal = False
    outcome = _choose(equal, "round_trip_equal", "round_trip_mismatch")
    outcomes.append(outcome)

    # There is one more candidate than declared names, so at least one is absent.
    declared_columns = {name.casefold() for name in names}
    candidates = (
        "no_such_column",
        *(f"no_such_column_{index}" for index in range(len(declared_columns))),
    )
    undeclared_column = next(filter(lambda name: name not in declared_columns, candidates))
    try:
        column_rows = connection.execute(f"SELECT {undeclared_column} FROM {table_name}").fetchall()
    except Exception:
        column_rows = None
    outcome = _choose(column_rows is None, "undeclared_column_rejected", "undeclared_column_accepted")
    outcomes.append(outcome)

    required = [
        name for name, _ in filter(
            lambda item: not _read_or(item[1], "nullable", True)
            and not _read_or(item[1], "primary_key", False),
            columns,
        )
    ]
    for missing in required[:1]:
        present = list(filter(lambda item: item[0] != missing, columns))
        remaining_names = [name for name, _ in present]
        remaining_values = [_row_value(column) for _, column in present]
        remaining_placeholders = ", ".join(["?"] * len(remaining_values))
        try:
            inserted = connection.execute(
                f"INSERT INTO {table_name} ({', '.join(remaining_names)}) VALUES ({remaining_placeholders})",
                remaining_values,
            )
        except Exception:
            inserted = None
        outcome = _choose(inserted is None, "missing_required_field_rejected", "missing_required_field_accepted")
        outcomes.append(outcome)

    try:
        rows = list(connection.execute(f"SELECT * FROM {table_name} WHERE 1 = 0").fetchall())
    except Exception:
        rows = None
    outcome = _choose(rows == [], "empty_rows", "empty_set_faulted")
    outcomes.append(outcome)
    return outcomes


# inherits: hd=python/honest-test/honest-test.hd::run_persist_schema_check -> feature=specs/features/honest-test.feature::run_persist_schema_check collects ordered findings from fresh databases -> test=python/honest-test/conformance/probe_run_persist_schema_check.py::probe_run_persist_schema_check
# hd: run_persist_schema_check
def run_persist_schema_check(schema, connect):
    """Judge the ordered outcomes of each table's fresh database."""
    return [
        finding
        for table_name, table in schema.items()
        for outcome in read_schema_probe(table_name, table, connect)
        for finding in schema_probe_findings(table_name, outcome)
    ]


# inherits: hd=python/honest-test/honest-test.hd::test_persist_schema_contract -> feature=specs/features/honest-test.feature::test_persist_schema_contract reports a valid empty-set read fault -> test=python/honest-test/conformance/probe_test_persist_schema_contract_empty_set_fault.py::probe_test_persist_schema_contract_empty_set_fault
# inherits: hd=python/honest-test/honest-test.hd::test_persist_schema_contract -> feature=specs/features/honest-test.feature::test_persist_schema_contract checks a schema against a real in-memory database -> test=python/honest-test/conformance/probe_test_persist_schema_contract.py::probe_test_persist_schema_contract
# hd: test_persist_schema_contract
def test_persist_schema_contract(schema, connect):
    """Return the persistence-contract findings for the supplied schema."""
    return run_persist_schema_check(schema, connect)
