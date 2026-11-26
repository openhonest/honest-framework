# scenario: register_message_type
"""Red test for the register_message_type scenario (specs/features/honest-alerts.feature).

The door

    register_message_type(message_type, message_versions, context, conn) -> RegisterResult | Fault   (awaited)

is the message-type registration door the world calls (honest-alerts.hd, boundary_in
register_message_type). It hands its input to run_register_message_type, whose write path runs
through write_registered_type into the module-owned alert_registered_types honest-persist table
(honest-alerts.hd, section 3b.1, 3b.3). This probe drives the real door against a REAL in-memory
SQLite connection and asserts directly against the COMMITTED rows of that table -- a SELECT count on
alert_registered_types -- never a stand-in for the write.

The alert_registered_types table is built from the module's own declared manifest,
alert_tables_schema() (honest-alerts.hd, fn alert_tables_schema, section 10b), exactly as
honest-observe's laws build the event-log table from event_log_schema(): the laws read the table
name and columns from the manifest rather than hardcoding the coder's schema, so the test and the
manifest cannot drift.

What the scenario fixes, read at the committed rows and at the door's return:

  - FIRST registration of a never-seen type writes exactly ONE row to alert_registered_types and
    returns the success RegisterResult echoing the message_type and the versions now recorded;
  - IDENTICAL re-registration (the arriving whole declaration byte-identical to the stored one)
    writes NOTHING -- the row count stays 1 -- and is still a success (action noop,
    honest-alerts.hd section 3b.3, RegisterDecision noop arm);
  - REFUSED (differing) re-registration writes NOTHING -- the row count stays 1 -- and returns a
    client Fault code "refused_registration" (spec section 6b) whose detail names the existing
    declaration against the arriving one.

A Fault here is honest-type's canonical fault record: is_err == True is the reserved arm tag
(honest-alerts.hd, type Fault), category is a FaultCategory member ("client"/"server"), and code is
the specific reason read from detail without parsing the message (section 6b). conn is a standard
DB-API connection (PEP 249), "held and passed, never read by any pure function"
(honest-alerts.hd, read_registered_type note); here it is a REAL sqlite3 in-memory connection whose
alert_registered_types table is created from the manifest before the door is called.

Pure, data-driven, no mocks of our own code and no data-holding test-double classes: plain dicts,
plain functions, a real sqlite conn. Faults are data -- the probe returns a list of failure strings
and is empty when every row holds.
"""

import asyncio
import sqlite3


# --- the alerts-owned registry table, built from the module's own manifest -----------------------


def _registered_types_manifest():
    """The alert_registered_types manifest out of alert_tables_schema() (honest-alerts.hd, section
    10b). The function returns the three alerts-owned table manifests as data; this finds the one for
    alert_registered_types without assuming the container shape (a dict keyed by table name, a dict of
    manifests, or a list of manifests), reading the table name off each manifest's own "table" key."""
    from honest_alerts import alert_tables_schema

    schema = alert_tables_schema()
    candidates = []
    if isinstance(schema, dict):
        # either {table_name: manifest, ...} or a single manifest with a "table" key
        if schema.get("table") == "alert_registered_types":
            return schema
        candidates = list(schema.values())
    elif isinstance(schema, (list, tuple)):
        candidates = list(schema)
    for manifest in candidates:
        if isinstance(manifest, dict) and manifest.get("table") == "alert_registered_types":
            return manifest
    raise KeyError(
        f"alert_tables_schema() carries no alert_registered_types manifest: {schema!r}"
    )


def _conn_with_registry():
    """A real in-memory sqlite connection whose alert_registered_types table is created from the
    module's declared manifest -- the integration boundary the door writes through, not a mock."""
    conn = sqlite3.connect(":memory:")
    manifest = _registered_types_manifest()
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
    conn.commit()
    return conn


def _registry_count(conn):
    """The committed row count of alert_registered_types, read straight off the real connection."""
    table = _registered_types_manifest()["table"]
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _is_fault(result):
    """The reserved is_err arm tag honest-type stamps on every Fault (honest-alerts.hd, type Fault)."""
    return isinstance(result, dict) and result.get("is_err") is True


def _register(message_type, message_versions, conn):
    """Call the real awaited door once and return its value."""
    from honest_alerts import register_message_type

    return asyncio.run(register_message_type(message_type, message_versions, {}, conn))


_TYPE = "approval.requested"


# --- Row 1: FIRST registration writes exactly one row and returns the success echo -----------------
def _probe_first_write():
    bad = []
    conn = _conn_with_registry()
    try:
        before = _registry_count(conn)
        got = _register(_TYPE, ["v1", "v2"], conn)
        after = _registry_count(conn)
    finally:
        conn.close()
    if before != 0:
        bad.append(f"alert_registered_types started with {before} rows, expected 0")
    if _is_fault(got):
        return bad + [
            f"register_message_type({_TYPE!r}, ['v1', 'v2']) -> Fault {got!r}; "
            f"expected a success RegisterResult on a first registration"
        ]
    if after != 1:
        bad.append(
            f"first registration left {after} committed alert_registered_types row(s), expected 1"
        )
    if not isinstance(got, dict):
        return bad + [
            f"register_message_type({_TYPE!r}, ['v1', 'v2']) -> {got!r}; expected a RegisterResult record"
        ]
    if got.get("message_type") != _TYPE:
        bad.append(f"success message_type -> {got.get('message_type')!r}, expected {_TYPE!r}")
    if got.get("message_versions") != ["v1", "v2"]:
        bad.append(
            f"success message_versions -> {got.get('message_versions')!r}, expected ['v1', 'v2']"
        )
    return bad


# --- Row 2: IDENTICAL re-registration writes nothing (count stays 1) and is a no-op success --------
def _probe_identical_noop():
    bad = []
    conn = _conn_with_registry()
    try:
        first = _register(_TYPE, ["v1", "v2"], conn)
        if _is_fault(first):
            return [
                f"register_message_type seed (first registration) -> Fault {first!r}; "
                f"expected a success so an identical re-registration can be a no-op"
            ]
        seeded = _registry_count(conn)
        second = _register(_TYPE, ["v1", "v2"], conn)
        after = _registry_count(conn)
    finally:
        conn.close()
    if seeded != 1:
        bad.append(f"after the first write there were {seeded} rows, expected 1")
    if _is_fault(second):
        return bad + [
            f"register_message_type({_TYPE!r}, ['v1', 'v2']) identical re-registration -> Fault "
            f"{second!r}; expected a no-op success (byte-identical declaration, section 3b.3)"
        ]
    if after != 1:
        bad.append(
            f"identical re-registration wrote a row: alert_registered_types now has {after}, "
            f"expected it to stay 1 (no-op, section 3b.3)"
        )
    return bad


# --- Row 3: REFUSED differing re-registration writes nothing and returns refused_registration ------
def _probe_refused_reregistration():
    bad = []
    conn = _conn_with_registry()
    try:
        first = _register(_TYPE, ["v1"], conn)
        if _is_fault(first):
            return [
                f"register_message_type seed (first registration) -> Fault {first!r}; "
                f"expected a success so a differing re-registration can be refused"
            ]
        seeded = _registry_count(conn)
        second = _register(_TYPE, ["v1", "v2"], conn)
        after = _registry_count(conn)
    finally:
        conn.close()
    if seeded != 1:
        bad.append(f"after the first write there were {seeded} rows, expected 1")
    if not _is_fault(second):
        return bad + [
            f"register_message_type({_TYPE!r}, ['v1', 'v2']) differing re-registration -> {second!r}; "
            f"expected a client Fault code 'refused_registration' (spec section 6b)"
        ]
    if after != 1:
        bad.append(
            f"refused re-registration wrote a row: alert_registered_types now has {after}, "
            f"expected it to stay 1 (nothing written on a refusal)"
        )
    if second.get("code") != "refused_registration":
        bad.append(
            f"differing re-registration -> code {second.get('code')!r}, "
            f"expected 'refused_registration' (spec section 6b)"
        )
    if second.get("category") != "client":
        bad.append(
            f"differing re-registration -> category {second.get('category')!r}, expected 'client'"
        )
    detail = second.get("detail")
    if not isinstance(detail, dict) or not detail:
        bad.append(
            f"differing re-registration -> detail {detail!r}, expected a non-empty mapping naming "
            f"the existing declaration against the arriving one (section 6b)"
        )
    return bad


def probe_register_message_type():
    """register_message_type writes exactly one alert_registered_types row and returns the success
    echo on a first registration; writes nothing (count stays 1) on a byte-identical re-registration,
    still a success; and writes nothing and returns a 'refused_registration'/client Fault on a
    differing re-registration -- all by return, never by raise (RegisterResult | Fault)."""
    bad = []
    bad.extend(_probe_first_write())
    bad.extend(_probe_identical_noop())
    bad.extend(_probe_refused_reregistration())
    return bad


if __name__ == "__main__":
    failures = probe_register_message_type()
    if failures:
        print(f"RED: {len(failures)} failure(s)")
        for line in failures:
            print(" -", line)
        raise SystemExit(1)
    print("GREEN: register_message_type door contract holds")
