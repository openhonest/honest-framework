# scenario: run_register_message_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_register_message_type -> feature=specs/features/honest-alerts.feature::run_register_message_type
"""Red test for the run_register_message_type scenario (honest-alerts.feature).

run_register_message_type(message_type, message_versions, context, conn) is the
single mutator of the registered-types record. It reads the existing registration
with read_registered_type, hands the arriving parts and the existing-or-NOTHING to
build_registered_type, and on a write decision persists through write_registered_type.
It returns RegisterResult | Fault and never raises.

This probe drives the module against a REAL in-memory SQLite connection
(sqlite3.connect(":memory:")). The alert_registered_types table is created on that
one connection from the module's OWN declared manifest, alert_tables_schema() (spec
section 10b) -- the honest-alerts twin of honest-observe's event_log_schema, built
the same way honest-observe's laws build the event-log table from its manifest. The
laws never hardcode the coder's table name or columns; they read them from the
manifest so the schema stays the one declared shape. The row count is then asserted
directly against the committed rows with a SELECT count on alert_registered_types.

The scenario fixes three behaviours, each pinned here:

  - FIRST registration: run_register_message_type writes exactly ONE row for the
    message_type and returns a RegisterResult echoing the type and the versions now
    recorded. Asserted by SELECT count -> 1.
  - IDENTICAL re-registration (byte-identical whole declaration): writes NOTHING, the
    row count stays 1, a no-op success returning the stored declaration.
  - REFUSED re-registration (a differing declaration): writes NOTHING, the row count
    stays 1, and returns a Fault with code refused_registration, category client
    (spec section 6b), whose detail names the existing versions against the arriving.

Honest form: cases are data; one async probe feeds each case to the real
run_register_message_type and returns a list of failure strings, empty when a case
holds. No data-holding test-double classes: the store is a real sqlite connection,
driven with plain functions and dicts. In-test I/O at the DB boundary (real
in-memory SQLite) is allowed. conn is `any` in the .hd (a PEP 249 connection) that
honest-alerts holds and passes; no pure function reads it.

honest-check (the honesty checker) could not be run against this fragment during the
clean-slate rebuild; the honesty is held to the rules by discipline here.
"""

import asyncio
import sqlite3

from honest_alerts import alert_tables_schema, run_register_message_type


_TABLE = "alert_registered_types"
_APPROVAL = "approval.requested"
_VERSIONS = ["v1", "v2"]


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _is_fault(value):
    """The fault arm carries the reserved is_err tag true (honest-type 13.2)."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


def _registered_types_manifest():
    """The single alert_registered_types manifest out of alert_tables_schema().

    The .hd declares three alerts-owned table manifests (alert_routes,
    alert_deliveries, alert_registered_types); the exact container shape is not
    pinned by the scenario (see GAPS). This reader accepts the manifests as a list of
    {table, columns, ...} records or as a dict keyed by table name, and finds the one
    whose table is alert_registered_types -- failing loudly if the module does not
    name it, rather than guessing a shape."""
    schema = alert_tables_schema()
    manifests = []
    if isinstance(schema, dict):
        # either {table_name: manifest} or a single manifest dict
        if schema.get("table") == _TABLE:
            return schema
        manifests = list(schema.values())
    elif isinstance(schema, (list, tuple)):
        manifests = list(schema)
    for m in manifests:
        if isinstance(m, dict) and m.get("table") == _TABLE:
            return m
    raise AssertionError(
        f"alert_tables_schema() does not name the {_TABLE} manifest: {schema!r}"
    )


def _open_conn_with_table():
    """A real in-memory SQLite connection with alert_registered_types created from
    the module's own manifest -- the honest-persist migration's one declared shape."""
    conn = sqlite3.connect(":memory:")
    manifest = _registered_types_manifest()
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {manifest['table']} ({columns})")
    conn.commit()
    return conn


def _row_count(conn):
    """Count the committed rows in alert_registered_types directly."""
    cur = conn.execute(f"SELECT count(*) FROM {_TABLE}")
    return cur.fetchone()[0]


# Each case runs a sequence on ONE real connection: an optional first registration to
# establish the stored row through the module's own write path, then the arriving
# registration whose outcome the scenario fixes, then the committed-row count the
# scenario fixes for the table after that call.
_CASES = [
    {
        "name": "first registration writes exactly one row and echoes the type and versions",
        "pre": [],
        "message_type": _APPROVAL,
        "message_versions": _VERSIONS,
        "outcome": "result",
        "expect_type": _APPROVAL,
        "expect_versions": _VERSIONS,
        "expect_rows": 1,
    },
    {
        "name": "byte-identical re-registration writes nothing (row count stays 1) and is a no-op success",
        "pre": [(_APPROVAL, _VERSIONS)],
        "message_type": _APPROVAL,
        "message_versions": _VERSIONS,
        "outcome": "result",
        "expect_type": _APPROVAL,
        "expect_versions": _VERSIONS,
        "expect_rows": 1,
    },
    {
        "name": "differing re-registration writes nothing (row count stays 1) and is refused: Fault refused_registration/client naming existing vs arriving",
        "pre": [(_APPROVAL, _VERSIONS)],
        "message_type": _APPROVAL,
        "message_versions": ["v1", "v3"],
        "outcome": "fault",
        "expect_code": "refused_registration",
        "expect_category": "client",
        "detail_must_name": ["v2", "v3"],
        "expect_rows": 1,
    },
]


async def _run_case(case):
    bad = []
    conn = _open_conn_with_table()

    # Establish stored state through the module's own write path.
    for pre_type, pre_versions in case["pre"]:
        pre_got = await run_register_message_type(pre_type, pre_versions, {}, conn)
        if _is_fault(pre_got):
            bad.append(
                f"{case['name']}: setup registration {pre_type}={pre_versions} returned a Fault {pre_got!r}"
            )
            return bad

    before = conn.execute(f"SELECT * FROM {_TABLE}").fetchall()
    if case["pre"]:
        for operation in ("INSERT", "UPDATE", "DELETE"):
            conn.execute(
                f"CREATE TRIGGER prevent_registration_{operation} BEFORE {operation} ON {_TABLE} "
                "BEGIN SELECT RAISE(ABORT, 're-registration must not write'); END"
            )
        conn.commit()

    got = await run_register_message_type(
        case["message_type"],
        case["message_versions"],
        {},
        conn,
    )

    if case["outcome"] == "result":
        if _is_fault(got):
            bad.append(f"{case['name']}: got a Fault {got!r}, expected a RegisterResult")
        else:
            mt = _field(got, "message_type")
            mv = _field(got, "message_versions")
            if mt != case["expect_type"]:
                bad.append(
                    f"{case['name']}: RegisterResult.message_type -> {mt!r}, expected {case['expect_type']!r}"
                )
            got_versions = list(mv) if mv is not None else None
            if got_versions != list(case["expect_versions"]):
                bad.append(
                    f"{case['name']}: RegisterResult.message_versions -> {mv!r}, expected {case['expect_versions']!r}"
                )
    else:  # fault
        if not _is_fault(got):
            bad.append(f"{case['name']}: got {got!r}, expected a Fault (is_err true)")
        else:
            code = _field(got, "code")
            category = _field(got, "category")
            if code != case["expect_code"]:
                bad.append(
                    f"{case['name']}: Fault.code -> {code!r}, expected {case['expect_code']!r}"
                )
            if category != case["expect_category"]:
                bad.append(
                    f"{case['name']}: Fault.category -> {category!r}, expected {case['expect_category']!r}"
                )
            blob = repr(_field(got, "detail") or {})
            for token in case["detail_must_name"]:
                if token not in blob:
                    bad.append(
                        f"{case['name']}: Fault.detail must name {token!r} (existing vs arriving), got {blob}"
                    )

    # The committed rows are the module's own state: assert the row count directly.
    rows = _row_count(conn)
    if rows != case["expect_rows"]:
        bad.append(
            f"{case['name']}: {_TABLE} row count -> {rows}, expected {case['expect_rows']}"
        )

    after = conn.execute(f"SELECT * FROM {_TABLE}").fetchall()
    if case["pre"] and after != before:
        bad.append(f"{case['name']}: stored registration changed from {before!r} to {after!r}")

    conn.close()
    return bad


def probe_run_register_message_type():
    """A first registration writes exactly one row and returns a RegisterResult
    echoing the type and the versions now recorded; a byte-identical re-registration
    writes nothing (the row count stays 1) and is a no-op success returning the stored
    declaration; a differing re-registration writes nothing (the row count stays 1)
    and is refused as a Fault (refused_registration, client) whose detail names the
    existing versions against the arriving."""
    bad = []
    loop = asyncio.new_event_loop()
    try:
        for case in _CASES:
            bad.extend(loop.run_until_complete(_run_case(case)))
    finally:
        loop.close()
    return bad


def run(_suite_path=None):
    failures = probe_run_register_message_type()
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
