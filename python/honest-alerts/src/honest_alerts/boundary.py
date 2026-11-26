"""The boundary: the readers that pull from the world, the output boundaries that write, the
orchestrators that compose the pure core with I/O, and the three unit-1 doors. I/O lives here; the
pure core in pure.py takes data and returns data (P03)."""

import json
import os
import uuid
import time

import honest_observe as HO

from honest_alerts._util import _get, _pick
from honest_alerts.faults import alert_tables_schema, alerts_fault
from honest_alerts.pure import build_ack_event, build_message, build_registered_type, supervise, uuid7_from_parts


NOTHING = None


# The one alert event schema version honest-alerts stamps on the alert.* events it appends. Named
# once so the version the emit seam carries is written in one place.
_ALERT_EVENT_VERSION = "1"


# A table manifest by name out of alert_tables_schema(): the table-touching readers and writers read
# their table name and columns from the manifest rather than hardcoding them (section 10b). A lambda,
# not a column-0 def, so it adds no declared function.
_table_manifest = lambda name: next(filter(lambda table: table["table"] == name, alert_tables_schema()))


# --- readers (pull from the world) -----------------------------------------------------------------

# inherits: hd=python/honest-alerts/honest-alerts.hd::new_message_id -> feature=specs/features/honest-alerts.feature::new_message_id -> test=python/honest-alerts/conformance/laws_new_message_id.py::probe_new_message_id
# hd: new_message_id
def new_message_id():
    """Pull one fresh message id from the random source, a UUID v7 that is time-ordered so messages
    sort by creation (section 3.1). run_send invokes it and applies its answer into the message under
    construction, so the id is assigned in one place. A reader, not a pure fn, because a fresh id is a
    read of the world: made pure it would be a hidden non-deterministic call, the leak the reader role
    exists to surface. RFC 9562 v7 layout: the leading 48 bits are the Unix epoch in milliseconds
    (time-ordered), the version nibble is 7, the variant bits are 0b10, and the remaining 74 bits are
    drawn from os.urandom so two calls in the same millisecond differ."""
    unix_ms = time.time_ns() // 1_000_000
    random_a = int.from_bytes(os.urandom(2), "big")
    random_b = int.from_bytes(os.urandom(8), "big")
    return uuid7_from_parts(unix_ms, random_a, random_b)


# hd: now
def now():
    """Pull the current wall-clock time as epoch seconds UTC (section 3.1, 6.1, 10). It reads the
    clock and nothing else. A reader for the same reason new_message_id is: a clock read inside a pure
    function is the hidden-clock leak the role declaration makes visible."""
    return int(time.time())


# A stored registered-types row decodes message_versions from JSON text back to the version list. A
# lambda over the raw row. A row of None (no record) is the NOTHING answer.
_decode_registered = lambda message_type, versions_text: {
    "message_type": message_type,
    "message_versions": json.loads(versions_text),
}


# hd: read_registered_type
async def read_registered_type(message_type, conn):
    """Read the registered-types table for the RegisteredType record of one message_type (section
    3b.2). It returns that type's RegisteredType, carrying the closed set of versions the registering
    application declared, or NOTHING when the type was never registered. conn is the injected PEP 249
    connection, held and passed. It reads the table name and columns from the alert_tables_schema
    manifest rather than hardcoding them (section 10b). run_send invokes it (a NOTHING answer or a
    version outside the set is a client fault build_message returns); run_register_message_type invokes
    it to read the existing registration before deciding the re-registration rule (section 3b.3)."""
    manifest = _table_manifest("alert_registered_types")
    table = manifest["table"]

    def _read():
        row = conn.execute(
            f"SELECT message_type, message_versions FROM {table} WHERE message_type = ?",
            (message_type,),
        ).fetchone()
        return _pick(row is None, lambda: NOTHING, lambda: _decode_registered(row[0], row[1]))

    # The registry table may not exist yet on a store with no alerts migration (the send door's
    # unregistered case): a missing table is a declared bounded case meaning no registration, the
    # NOTHING answer, decided by reading sqlite_master rather than by catching a query exception, so
    # absence is a visible branch (P16), not a swallowed defect.
    present = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()[0]
    return _pick(present == 0, lambda: NOTHING, _read)


# hd: read_routes
async def read_routes(message_type, conn):
    """Read the alert_routes routing table for the routes that could match a message type (section 5,
    6.1). The read returns every AlertRoute whose message_type matches it or wildcard-matches it, which
    the pure supervisor then filters and sorts, so the match decision lives in the pure core. conn is
    the injected PEP 249 connection. It reads the alert_routes table name and columns from the
    alert_tables_schema manifest rather than hardcoding them (section 10b). run_send invokes it and
    passes the routes to supervise."""
    manifest = _table_manifest("alert_routes")
    table = manifest["table"]
    columns = manifest["columns"]
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    return [_decode_route(dict(zip(columns, row))) for row in rows]


# One stored alert_routes row decodes its JSON-text columns (channels, escalation) and its integer
# priority back to an AlertRoute; a null escalation stays NOTHING. A lambda over the raw column map.
_decode_json = lambda text: _pick(text is None, lambda: NOTHING, lambda: json.loads(text))
_decode_route = lambda raw: {
    "route_id": raw["route_id"],
    "message_type": raw["message_type"],
    "sender_type": _pick(raw["sender_type"] is None, lambda: NOTHING, lambda: raw["sender_type"]),
    "channels": _decode_json(raw["channels"]),
    "escalation": _decode_json(raw["escalation"]),
    "priority": int(raw["priority"]),
}


# --- output boundaries (write) ---------------------------------------------------------------------

# A JSON-structured column is stored as JSON text, a scalar as its value: the one place the delivery
# and registry writes serialize a column by its declared kind. Named once.
_JSON_COLUMNS = {"channels", "escalation", "message_versions", "recipient"}
_to_cell = lambda column, value: _pick(
    column in _JSON_COLUMNS, lambda: json.dumps(value), lambda: _pick(value is None, lambda: None, lambda: str(value))
)


# hd: write_delivery
async def write_delivery(delivery, conn):
    """Write one pending delivery record into the alert_deliveries queue table through honest-persist
    (section 6.1). delivery is one Delivery the supervisor produced, status pending. It is a terminus:
    it does only the write and returns honest-persist's own insert outcome; it constructs no Fault and
    reads nothing, and it does not commit -- run_send commits once so the rows and the alert.sent
    append share one transaction (section 6.1). It reads the table name and columns from the
    alert_tables_schema manifest rather than hardcoding them (section 10b). run_send invokes it once
    per delivery in the plan."""
    manifest = _table_manifest("alert_deliveries")
    table = manifest["table"]
    columns = manifest["columns"]
    # delivery_id is this row's key; the supervisor's Delivery carries no id, so the write mints one
    # fresh here at the write boundary, the single place the queue row is formed.
    row = dict(delivery)
    row["delivery_id"] = str(uuid.uuid4())
    values = tuple(_to_cell(column, _get(row, column, None)) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
    return {"ok": True}


# inherits: hd=python/honest-alerts/honest-alerts.hd::write_registered_type -> feature=specs/features/honest-alerts.feature::write_registered_type -> test=python/honest-alerts/conformance/laws_write_registered_type.py::probe_write_registered_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::write_registered_type -> feature=specs/features/honest-alerts.feature::write_registered_type returns a refused insert reason without ending the transaction -> test=python/honest-alerts/conformance/laws_write_registered_type_insert_refused.py::probe_write_registered_type_insert_refused
# hd: write_registered_type
async def write_registered_type(registered_type, conn):
    """Write and commit one registration. A driver refusal preserves the caller's transaction."""
    manifest = _table_manifest("alert_registered_types")
    table = manifest["table"]
    columns = manifest["columns"]
    values = tuple(_to_cell(column, _get(registered_type, column, None)) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    # PEP 249 drivers can expose their own IntegrityError on the connection.
    refusal = getattr(conn, "IntegrityError", ())
    try:
        conn.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
    except refusal as error:
        return {"ok": False, "reason": str(error)}
    conn.commit()
    return {"ok": True}


# hd: emit
async def emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn):
    """The emit seam into honest-observe: honest-alerts calls honest-observe's frozen emit door to
    append one alert.* event to the event log (section 6.1, 10; honest-observe section 3). Its
    signature is honest-observe.emit's contract exactly as frozen on main, and honest-alerts builds to
    that contract without redefining or widening it; the return is honest-observe's own Event-or-Fault,
    carried out as any. It is a terminus that does only the append; run_send invokes it for alert.sent
    and run_acknowledge for alert.acknowledged. honest-observe's emit returns a Fault for a present
    event-log table whose append is rejected, and raises only when the table is absent; this terminus
    catches that one boundary exception here, at the I/O edge, and returns it as a server Fault by
    value, so a failed append always travels to the orchestrator by return and never past this seam as
    a raise (P24)."""
    try:
        return await HO.emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn)
    except Exception as exc:
        return alerts_fault(
            code="emit_seam_failed",
            message="the honest-observe emit append raised at the event-log boundary; the event was not appended",
            category="server",
            detail={"aggregate_id": aggregate_id, "event_type": event_type, "detail": str(exc)},
        )


# Recognize honest-observe's Fault arm (and honest-alerts' own) by the reserved is_err tag. A lambda.
_is_err = lambda value: isinstance(value, dict) and value.get("is_err") is True


# --- orchestrators ---------------------------------------------------------------------------------

# inherits: hd=python/honest-alerts/honest-alerts.hd::run_register_message_type -> feature=specs/features/honest-alerts.feature::run_register_message_type -> test=python/honest-alerts/conformance/laws_run_register_message_type.py::probe_run_register_message_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_register_message_type -> feature=specs/features/honest-alerts.feature::run_register_message_type returns an actionable fault when the store write fails -> test=python/honest-alerts/conformance/laws_run_register_message_type_write_failed.py::probe_run_register_message_type_write_failed
# hd: run_register_message_type
async def run_register_message_type(message_type, message_versions, context, conn):
    """Read and validate a registration, then persist a first registration or return a fault."""
    existing = await read_registered_type(message_type, conn)
    decision = build_registered_type(message_type, message_versions, existing)
    match _is_err(decision):
        case True:
            return decision

    registered = decision["registered_type"]
    result = {"message_type": registered["message_type"], "message_versions": registered["message_versions"]}
    match decision["action"]:
        case "noop":
            return result

    outcome = await write_registered_type(registered, conn)
    return _pick(
        outcome["ok"],
        lambda: result,
        lambda: alerts_fault(
            code="registration_write_failed",
            message="the registered-types store write failed; retry the registration or check the connection",
            category="server",
            detail={"message_type": message_type, "reason": outcome["reason"]},
        ),
    )


# inherits: hd=python/honest-alerts/honest-alerts.hd::run_send -> feature=specs/features/honest-alerts.feature::run_send -> test=python/honest-alerts/conformance/laws_run_send.py::probe_run_send
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_send -> feature=specs/features/honest-alerts.feature::run_send returns an actionable fault when the event append rolls back -> test=python/honest-alerts/conformance/laws_run_send_append_failed.py::probe_run_send_append_failed
# hd: run_send
async def run_send(message_type, recipient, payload, opts, context, conn):
    """Write deliveries and append alert.sent in one transaction."""
    message_id = new_message_id()
    sent_at = now()
    sender = _get(context, "sender", NOTHING)
    registered = await read_registered_type(message_type, conn)
    message = build_message(message_type, recipient, payload, opts, sender, message_id, sent_at, False, registered)
    match _is_err(message):
        case True:
            return message

    routes = await read_routes(message_type, conn)
    plan = supervise(message, routes)
    for delivery in plan["deliveries"]:
        await write_delivery(delivery, conn)
    # The successful emit commits both the delivery rows and the event on the same connection.
    appended = await emit("alert.sent", "alert", message_id, message, context, _ALERT_EVENT_VERSION, conn)
    match _is_err(appended):
        case True:
            conn.rollback()
            return alerts_fault(
                code="append_failed",
                message="the alert.sent append to the event log failed and the send was rolled back. "
                        "Check the event-log connection and retry the send.",
                category="server",
                detail={"message_id": message_id},
            )
    return {"delivered": len(plan["deliveries"])}


# hd: run_acknowledge
async def run_acknowledge(message_id, actor_ref, reply_payload, session, acknowledged_at, context, conn):
    """Run the acknowledge path, the single mutator of the acknowledgment event (section 9.1, 10). It
    hands message_id, actor_ref, reply_payload, session and acknowledged_at to build_ack_event, the
    pure function that assembles the alert.acknowledged payload, then emits alert.acknowledged through
    the emit seam with the message_id as aggregate_id, so the event folds under the same aggregate as
    the alert.sent and feeds the mailbox projection that terminates the message. It returns AckResult on
    a clean emit, or a Fault code ack_append_failed (category server) when the append fails. It returns
    AckResult | Fault so a failed acknowledge bubbles to the door by return."""
    ack_payload = build_ack_event(message_id, actor_ref, reply_payload, session, acknowledged_at)
    # The emit seam appends alert.acknowledged and returns a server Fault by value on any failed append
    # (the seam converts a raised boundary exception to a Fault at the I/O edge). A failed append
    # surfaces as this orchestrator's own ack_append_failed server Fault.
    appended = await emit("alert.acknowledged", "alert", message_id, ack_payload, context, _ALERT_EVENT_VERSION, conn)
    return _pick(
        _is_err(appended),
        lambda: alerts_fault(
            code="ack_append_failed",
            message="the alert.acknowledged append to the event log failed; retry the acknowledge or check the connection",
            category="server",
            detail={"message_id": message_id, "observe": appended.get("code")},
        ),
        lambda: {"message_id": message_id, "acknowledged": True},
    )


# --- doors (the world calls in here; nothing inside the module calls them) -------------------------

# hd: register_message_type
async def register_message_type(message_type, message_versions, context, conn):
    """The message-type registration door: a registering application declares the closed set of
    message_version values a message_type supports before sending any message of that type (section
    3b.1). The world calls in here and nothing inside the module calls it; it hands its input to
    run_register_message_type and returns what it returns. It returns RegisterResult echoing the type
    and the versions now recorded, or a Fault, never raising. One of the three unit-1 doors."""
    return await run_register_message_type(message_type, message_versions, context, conn)


# hd: send
async def send(message_type, recipient, payload, opts, context, conn):
    """The primary send door: fire and forget with respect to the sender (section 8.1). The world calls
    in here and nothing inside the module calls it; it hands its input to run_send and returns what
    run_send returns. It returns SendResult (the count of deliveries queued) or a Fault, never raising,
    because the calling link decides whether a failed send stops its chain."""
    return await run_send(message_type, recipient, payload, opts, context, conn)


# hd: acknowledge
async def acknowledge(message_id, actor_ref, reply_payload, session, acknowledged_at, context, conn):
    """The acknowledge door: records that a recipient acted on a message so the message can terminate
    (section 9.1, 10). The world calls in here and nothing inside the module calls it; it hands its
    input to run_acknowledge and returns what it returns. It returns AckResult or a Fault, never
    raising, for the same reason send does. One of the three unit-1 doors; there is no read_mailbox
    door, because reading a mailbox is a pure projection reached by import (section 4.1)."""
    return await run_acknowledge(message_id, actor_ref, reply_payload, session, acknowledged_at, context, conn)
