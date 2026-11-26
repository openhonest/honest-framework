# scenario: write_registered_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::write_registered_type -> feature=specs/features/honest-alerts.feature::write_registered_type
"""Red test fragment for the write_registered_type scenario (honest-alerts, section 3b.1, 10b).

Honest, data-driven, pure-probe. Cases are rows: each row a RegisteredType to write and the
row that must be committed to the alerts-owned registry table. One pure probe feeds each row
to the REAL write_registered_type (imported and called, no mock, no patched boundary), using a
REAL in-memory SQLite connection as the injected DB-API conn, and returns a list of failure
strings, empty when the case holds. No classes, no hidden state; records are plain dicts.

write_registered_type(registered_type: RegisteredType, conn: any) -> any
  (output boundary, awaited; writes one row into alert_registered_types through the injected
   PEP 249 conn; a terminus that does only the write and reads nothing.)

A RegisteredType is a flat record {message_type: str, message_versions: list<str>} (honest-alerts
section 3b.1). The alerts-owned registry table name and its columns are read from the
alert_tables_schema() manifest, not hardcoded here -- the same manifest the boundary reads, so the
test's table and the write cannot drift (section 10b). The manifest declares message_versions as
JSON text (the closed set of version strings), so the committed cell is JSON-decoded before it is
compared to the list.

What the scenario (feature lines for write_registered_type) fixes:
  - write_registered_type writes one RegisteredType record into the module-owned registered-types
    table through the injected conn, awaited because the insert is I/O;
  - it reaches that table by the name and columns from the alert_tables_schema manifest;
  - after the write the row is committed: selecting message_type back yields the dot-namespaced
    message_type written, and the message_versions cell carries the closed version set written.

The behaviour this probe can catch: a stub body `async def write_registered_type(...): return None`
writes no row, so the SELECT finds nothing and every literal case below fails. The probe is not
vacuous.
"""

import asyncio
import json
import sqlite3

from honest_alerts import alert_tables_schema, write_registered_type


def _registry_manifest():
    """The alert_registered_types manifest, read from the real schema function (not hardcoded)."""
    for table in alert_tables_schema():
        if table["table"] == "alert_registered_types":
            return table
    raise LookupError("alert_tables_schema() has no alert_registered_types manifest")


def _fresh_conn():
    """A real in-memory SQLite conn with the alerts registry table built from the manifest columns.

    The table name and the column names come from the manifest, so this mirrors exactly what the
    boundary reads. message_type is the key; both columns are TEXT (message_versions is JSON text
    per section 3b/10b).
    """
    manifest = _registry_manifest()
    table = manifest["table"]
    columns = manifest["columns"]
    conn = sqlite3.connect(":memory:")
    col_defs = []
    for column in columns:
        if column == "message_type":
            col_defs.append(f"{column} TEXT PRIMARY KEY")
        else:
            col_defs.append(f"{column} TEXT")
    conn.execute(f"CREATE TABLE {table} ({', '.join(col_defs)})")
    return conn, table


def _decode_versions(cell):
    """The manifest declares message_versions as JSON text; decode it, tolerating a raw list."""
    if isinstance(cell, (list, tuple)):
        return list(cell)
    try:
        return json.loads(cell)
    except (TypeError, ValueError):
        return cell


# Each row is one RegisteredType to write and the committed values it must produce. Both rows pin
# concrete, non-trivial literals the scenario fixes (a real message_type and a non-empty closed
# version set), so a stub that writes nothing fails the SELECT-back on both rows.
_CASES = [
    {
        "name": "write approval.requested with versions v1,v2 -> committed row round-trips",
        "registered_type": {"message_type": "approval.requested", "message_versions": ["v1", "v2"]},
        "expect_message_type": "approval.requested",
        "expect_versions": ["v1", "v2"],
    },
    {
        "name": "write escalation.raised with a single version v3 -> committed row round-trips",
        "registered_type": {"message_type": "escalation.raised", "message_versions": ["v3"]},
        "expect_message_type": "escalation.raised",
        "expect_versions": ["v3"],
    },
]


def probe_write_registered_type():
    """write_registered_type commits one RegisteredType row into the alerts-owned registry table
    (reached by the alert_tables_schema manifest name and columns) through the injected conn, so
    the row selects back with the message_type written and the closed version set written."""
    bad = []
    manifest = _registry_manifest()

    for case in _CASES:
        conn, table = _fresh_conn()
        try:
            asyncio.run(write_registered_type(case["registered_type"], conn))
        except Exception as exc:  # the boundary must do the write, not raise
            bad.append(f"{case['name']}: write_registered_type raised {exc!r}")
            conn.close()
            continue

        rows = conn.execute(
            f"SELECT message_type, message_versions FROM {table} "
            f"WHERE message_type = ?",
            (case["expect_message_type"],),
        ).fetchall()
        conn.close()

        if len(rows) != 1:
            bad.append(
                f"{case['name']}: expected exactly one committed row for "
                f"{case['expect_message_type']!r}, found {len(rows)}"
            )
            continue

        got_type, got_versions_cell = rows[0]
        if got_type != case["expect_message_type"]:
            bad.append(
                f"{case['name']}: committed message_type -> {got_type!r}, "
                f"expected {case['expect_message_type']!r}"
            )
        got_versions = _decode_versions(got_versions_cell)
        if got_versions != case["expect_versions"]:
            bad.append(
                f"{case['name']}: committed message_versions -> {got_versions!r}, "
                f"expected {case['expect_versions']!r}"
            )

    return bad


if __name__ == "__main__":
    import sys

    failures = probe_write_registered_type()
    if failures:
        for line in failures:
            print("FAIL:", line)
        sys.exit(1)
    print("ok: write_registered_type probe passed")
