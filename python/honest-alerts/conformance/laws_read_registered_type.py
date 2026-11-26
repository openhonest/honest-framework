# scenario: read_registered_type
"""Red test for the read_registered_type scenario (honest-alerts.feature).

read_registered_type(message_type, conn) is a reader that reads the registered-types
table (alert_registered_types) from honest-persist for the RegisteredType record of one
message_type. It returns that type's RegisteredType -- carrying the closed set of versions
the registering application declared -- or NOTHING (None) when the type was never
registered (spec sections 3b.1, 3b.2, 10b).

This probe drives the real module against a REAL in-memory SQLite connection
(sqlite3.connect(":memory:")). The alert_registered_types table is created on that one
connection from the module's OWN declared manifest, alert_tables_schema() (spec section
10b) -- the laws never hardcode the coder's table name; they read it from the manifest so
the read and the manifest cannot drift. One registered-type row is seeded directly so the
read path is the only function under test (no round-trip through the write boundary that
would let read and write move together). The row stores message_versions as a JSON array
text, the column shape the manifest declares.

The scenario fixes two behaviours, each pinned here:

  - a REGISTERED message_type: read_registered_type returns the stored RegisteredType,
    whose message_type equals the seeded type and whose message_versions equals the exact
    seeded closed set (a concrete non-trivial literal: ["v1", "v2"]).
  - an UNREGISTERED message_type (the absence case, written out explicitly): there is no
    row for it, so the reader returns NOTHING (None), not a record and not a Fault.

Honest form: cases are data; one async probe feeds each case to the real
read_registered_type and returns a list of failure strings, empty when a case holds. No
data-holding test-double classes: the store is a real sqlite connection, driven with plain
functions and dicts. In-test I/O at the DB boundary (real in-memory SQLite) is allowed.
conn is `any` in the .hd (a PEP 249 connection) honest-alerts holds and passes; no pure
function reads it. read_registered_type is awaited (async), so the probe runs it on an
event loop.

A stub body `return None` (or `return []`) would make the absence case pass but the
registered case fail (it expects a record with message_type "approval.requested" and
versions ["v1", "v2"]), so the probe is not vacuous.

honest-check (the honesty checker) could not be run against this fragment during the
clean-slate rebuild; the honesty is held to the rules by discipline here.
"""

import asyncio
import json
import sqlite3

from honest_alerts import alert_tables_schema, read_registered_type


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

    The .hd declares three alerts-owned table manifests; the exact container shape is not
    pinned by the scenario (see GAPS). This reader accepts the manifests as a list of
    {table, columns, ...} records or as a dict keyed by table name, and finds the one whose
    table is alert_registered_types -- failing loudly if the module does not name it,
    rather than guessing a shape."""
    schema = alert_tables_schema()
    manifests = []
    if isinstance(schema, dict):
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
    """A real in-memory SQLite connection with alert_registered_types created from the
    module's own manifest -- the honest-persist migration's one declared shape."""
    conn = sqlite3.connect(":memory:")
    manifest = _registered_types_manifest()
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {manifest['table']} ({columns})")
    conn.commit()
    return conn


def _seed(conn, message_type, versions):
    """Seed one registered-type row directly, so the read path is the only function under
    test. message_versions is stored as a JSON array text, the column the manifest
    declares for the closed version set."""
    conn.execute(
        f"INSERT INTO {_TABLE} (message_type, message_versions) VALUES (?, ?)",
        (message_type, json.dumps(versions)),
    )
    conn.commit()


# Each case seeds the stored rows, then reads one message_type and fixes the outcome.
_CASES = [
    {
        "name": "a registered message_type returns the stored RegisteredType (message_type + versions)",
        "seed": [(_APPROVAL, _VERSIONS)],
        "read": _APPROVAL,
        "outcome": "record",
        "expect_type": _APPROVAL,
        "expect_versions": _VERSIONS,
    },
    {
        "name": "an unregistered message_type returns NOTHING (None), not a record and not a Fault",
        "seed": [(_APPROVAL, _VERSIONS)],
        "read": "approval.never_registered",
        "outcome": "nothing",
    },
]


async def _run_case(case):
    bad = []
    conn = _open_conn_with_table()
    for seed_type, seed_versions in case["seed"]:
        _seed(conn, seed_type, seed_versions)

    got = await read_registered_type(case["read"], conn)

    if case["outcome"] == "record":
        if got is None:
            bad.append(f"{case['name']}: read returned None, expected a stored RegisteredType")
        elif _is_fault(got):
            bad.append(f"{case['name']}: read returned a Fault {got!r}, expected a RegisteredType")
        else:
            mt = _field(got, "message_type")
            mv = _field(got, "message_versions")
            if mt != case["expect_type"]:
                bad.append(
                    f"{case['name']}: RegisteredType.message_type -> {mt!r}, expected {case['expect_type']!r}"
                )
            got_versions = list(mv) if mv is not None else None
            if got_versions != list(case["expect_versions"]):
                bad.append(
                    f"{case['name']}: RegisteredType.message_versions -> {mv!r}, expected {case['expect_versions']!r}"
                )
    else:  # nothing (the absence case)
        if got is not None:
            bad.append(
                f"{case['name']}: read returned {got!r}, expected NOTHING (None) for an unregistered type"
            )

    conn.close()
    return bad


def probe_read_registered_type():
    """read_registered_type returns the stored RegisteredType -- its message_type and the
    exact closed set of versions -- for a registered message_type, and returns NOTHING
    (None) for a message_type that was never registered."""
    bad = []
    loop = asyncio.new_event_loop()
    try:
        for case in _CASES:
            bad.extend(loop.run_until_complete(_run_case(case)))
    finally:
        loop.close()
    return bad


def run(_suite_path=None):
    failures = probe_read_registered_type()
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
