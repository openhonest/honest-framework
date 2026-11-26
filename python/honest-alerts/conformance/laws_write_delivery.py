# scenario: write_delivery
"""Red test for the write_delivery scenario of honest-alerts (specs/features/honest-alerts.feature).

write_delivery is an output boundary (honest-alerts.hd, section 6.1, role boundary_out, awaited):

  "it is an output boundary that writes one pending delivery record into the alert_deliveries queue
   table through honest-persist, awaited because the insert is I/O"
  "delivery is one Delivery the supervisor produced, status pending"
  "conn is a standard DB-API connection (PEP 249), the injected honest-persist connection"
  "it is a terminus: it does only the write and returns honest-persist's own insert outcome; it
   constructs no Fault and reads nothing"
  "it writes database:given, honest-alerts' own alert_deliveries table, reading that table name and
   columns from the alert_tables_schema manifest rather than hardcoding them"

THE REAL DB. conn is a PEP-249 connection. This probe drives the REAL write_delivery against a REAL
in-memory sqlite connection -- never a mock of our own code. The alert_deliveries table is CREATEd from
the module's OWN declared manifest (alert_tables_schema()), so the probe never hardcodes the coder's
columns and the write-side and the manifest cannot drift (the exact point the scenario fixes).

THE ASSERTION is made against the pending row read back off the real conn with SELECT -- not the
value write_delivery returns, so there is no circular oracle and the assertion is the observed effect
of the boundary, exactly what a boundary_out is tested by. The probe SELECTs the row carrying the
Delivery's message_id and checks the Delivery's own fields landed: route_id, channel, deliver_at and
status pending (recipient is stored as JSON text, so it is compared parsed). These are literal,
non-trivial expected values the scenario fixes (status pending from the Delivery; the other fields are
the Delivery's own data, which the write must carry verbatim), so the probe is not vacuous: a stub body
(return []/None that writes nothing) commits no row, so the SELECT finds nothing and the probe fails.

The .hd signature is write_delivery(delivery, conn), awaited.

Run directly:
  cd python && uv run --package honest-alerts \
    python honest-alerts/conformance/laws_write_delivery.py
"""

import asyncio
import json
import sqlite3

from honest_alerts import alert_tables_schema, write_delivery


# ---------------------------------------------------------------------------------------------------
# Builders. No default kwargs: every Delivery field is passed explicitly, absence written as NOTHING
# (None), per the Delivery / ActorRef schemas (honest-alerts.hd). The builders take all fields as
# required arguments for that reason.
# ---------------------------------------------------------------------------------------------------

def _actor(type_, id_, tenant_id):
    """A flat ActorRef (honest-alerts.hd type ActorRef): pure identity, no session, no defaults."""
    return {"type": type_, "id": id_, "tenant_id": tenant_id}


def _delivery(message_id, route_id, channel, recipient, deliver_at, status):
    """One Delivery (honest-alerts.hd type Delivery): exactly its six fields, each passed explicitly,
    the record supervise produced with status pending."""
    return {
        "message_id": message_id,
        "route_id": route_id,
        "channel": channel,
        "recipient": recipient,
        "deliver_at": deliver_at,
        "status": status,
    }


# ---------------------------------------------------------------------------------------------------
# The real DB-API connection. alert_deliveries is created from the module's own declared manifest
# (alert_tables_schema()), so the probe reads the table name and columns as data rather than hardcoding
# them. recipient is a JSON structure stored as JSON text, per the alert_tables_schema note.
# ---------------------------------------------------------------------------------------------------

_JSON_COLUMNS = {"recipient"}


def _table_manifest(name):
    """The manifest for one alerts-owned table out of alert_tables_schema()'s three (honest-alerts.hd
    alert_tables_schema note): a record naming the table and its columns, read as data."""
    manifest = alert_tables_schema()
    tables = manifest["tables"] if isinstance(manifest, dict) and "tables" in manifest else manifest
    for table in tables:
        if table["table"] == name:
            return table
    raise LookupError(f"alert_tables_schema() declared no table named {name!r}: {manifest!r}")


def _conn():
    """A real in-memory sqlite connection carrying alert_deliveries, created from its declared manifest,
    every column TEXT (the laws_run_send.py / laws_ho.py idiom)."""
    conn = sqlite3.connect(":memory:")
    manifest = _table_manifest("alert_deliveries")
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {manifest['table']} ({columns})")
    conn.commit()
    return conn


def _delivery_row(conn, message_id):
    """The committed alert_deliveries row for one message_id, read back off the real conn as a column
    -> value map. Returns ("row", mapping) when one row was found, ("none", n) when n rows matched other
    than exactly one, ("query_error", exc) when the read failed -- a failed read is surfaced as a failed
    assertion, never collapsed into a missing row."""
    manifest = _table_manifest("alert_deliveries")
    cols = manifest["columns"]
    try:
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM {manifest['table']} WHERE message_id = ?",
            (message_id,),
        ).fetchall()
    except Exception as exc:  # a failed read is surfaced, never read as a missing row
        return ("query_error", exc)
    if len(rows) != 1:
        return ("none", len(rows))
    mapping = {}
    for col, value in zip(cols, rows[0]):
        if col in _JSON_COLUMNS and value is not None:
            mapping[col] = json.loads(value)
        else:
            mapping[col] = value
    return ("row", mapping)


# ---------------------------------------------------------------------------------------------------
# The case is data: one Delivery stated in full and the pending-row fields its write must produce on
# the real connection. One case, because the scenario fixes exactly one behaviour (write one pending
# delivery). The expected field values are literal and non-trivial (the Delivery's own data plus status
# pending), so a stub that writes nothing fails the SELECT-back assertion.
# ---------------------------------------------------------------------------------------------------

_DELIVERY = _delivery(
    message_id="m1",
    route_id="r1",
    channel="dom",
    recipient=_actor("user", "u1", None),
    deliver_at=1000,
    status="pending",
)

# The fields the pending row must carry, keyed by manifest column. deliver_at is an integer in the
# Delivery; stored in a TEXT column it comes back as its text form, so it is compared as str. recipient
# is compared parsed from JSON text. message_id is the SELECT key and is checked too.
_EXPECT_FIELDS = {
    "message_id": "m1",
    "route_id": "r1",
    "channel": "dom",
    "recipient": {"type": "user", "id": "u1", "tenant_id": None},
    "deliver_at": "1000",
    "status": "pending",
}


def _run(delivery, conn):
    """Call the real write_delivery once, awaiting it (the .hd marks write_delivery awaited). Returns
    ('ok', value) or ('raised', exc)."""
    try:
        return ("ok", asyncio.run(write_delivery(delivery, conn)))
    except Exception as exc:
        return ("raised", exc)


def probe_write_delivery():
    """write_delivery writes the one pending Delivery into the alert_deliveries table on the given conn,
    reading the table name and columns from alert_tables_schema()'s manifest, so the pending row (read
    back by SELECT) carries the Delivery's fields with status pending. The effect is observed on the real
    connection, not inferred from the returned value."""
    bad = []
    conn = _conn()
    kind, result = _run(_DELIVERY, conn)
    if kind == "raised":
        bad.append(
            f"write_delivery({_DELIVERY['message_id']}) raised {type(result).__name__}: {result}; a "
            f"terminus boundary does the write and returns honest-persist's outcome, it constructs no "
            f"Fault and must not fail on a present, writable alert_deliveries table"
        )
        conn.close()
        return bad

    if result != {"ok": True} or result["ok"] is not True:
        bad.append(f"write_delivery returned {result!r}, expected a successful {{ok: True}} outcome")

    if not conn.in_transaction:
        bad.append("write_delivery closed the transaction before the caller could commit it")

    outcome, detail = _delivery_row(conn, _DELIVERY["message_id"])
    conn.rollback()
    table = _table_manifest("alert_deliveries")["table"]
    remaining = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    if remaining != 0:
        bad.append(f"caller rollback left {remaining} delivery row(s), expected 0")
    if outcome == "query_error":
        bad.append(
            f"write_delivery({_DELIVERY['message_id']}) left alert_deliveries unreadable: "
            f"{type(detail).__name__}: {detail}. An unreadable table is a failed assertion, never "
            f"evidence of a missing write"
        )
        return bad
    if outcome == "none":
        bad.append(
            f"write_delivery({_DELIVERY['message_id']}) wrote {detail} alert_deliveries row(s) for "
            f"message_id m1, expected exactly 1: the boundary must write the one pending delivery"
        )
        return bad

    row = detail
    for col, expected in _EXPECT_FIELDS.items():
        if row.get(col) != expected:
            bad.append(
                f"write_delivery({_DELIVERY['message_id']}) wrote {col} = {row.get(col)!r}, "
                f"expected {expected!r}: the Delivery's own fields (status pending) must land in the row"
            )
    return bad



def probe_write_delivery_assigns_distinct_ids():
    """Each pending row has a delivery key and remains in the caller's transaction."""
    second = _delivery("m2", "r2", "dom", _actor("user", "u2", None), 1001, "pending")
    conn = _conn()
    try:
        for delivery in (_DELIVERY, second):
            outcome, result = _run(delivery, conn)
            if outcome == "raised":
                return [f"write_delivery({delivery['message_id']!r}) raised {result!r}"]
        table = _table_manifest("alert_deliveries")["table"]
        rows = conn.execute(f"SELECT message_id, delivery_id FROM {table} ORDER BY message_id").fetchall()
        pending = conn.in_transaction
        conn.rollback()
        remaining = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()

    failures = []
    if [message_id for message_id, _ in rows] != ["m1", "m2"]:
        failures.append(f"expected one stored delivery per call, got {rows!r}")
    delivery_ids = [delivery_id for _, delivery_id in rows]
    if any(not delivery_id for delivery_id in delivery_ids) or len(set(delivery_ids)) != len(delivery_ids):
        failures.append(f"expected populated, distinct stored delivery IDs, got {delivery_ids!r}")
    if not pending or remaining != 0:
        failures.append(
            f"delivery writes left transaction open={pending!r} and {remaining} rows after rollback"
        )
    return failures


if __name__ == "__main__":
    failures = probe_write_delivery() + probe_write_delivery_assigns_distinct_ids()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)
