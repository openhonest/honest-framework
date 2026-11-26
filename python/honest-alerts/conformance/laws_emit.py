# scenario: emit
# inherits: hd=python/honest-alerts/honest-alerts.hd::emit -> feature=specs/features/honest-alerts.feature::emit
"""Red test for the `emit` scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clause under test:
  "it is the emit seam into honest-observe: it calls honest-observe's frozen emit door to append one
   alert.* event to the event log ... aggregate_type is always alert and aggregate_id is the
   message_id ... payload is the Message on alert.sent ... it is a terminus that does only the
   append." The .hd signature is the frozen honest-observe.emit contract exactly:
   `emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn) -> any`.

`emit` is an output-boundary seam, so it is tested by asserting the effect it records: after calling
the REAL `emit`, the event must have landed in honest-observe's event log. The test builds the event
log in a REAL in-memory SQLite from honest-observe's `event_log_schema()` manifest (honest-observe is
a real dependency, not mocked), calls the real `emit` to append one alert.sent event, and then SELECTs
the row back out of the log, asserting its event_type, aggregate_id and payload match what was emitted.

No mock, no data-holding double: a real sqlite3 connection, plain dicts, plain functions. The DB
boundary I/O happens inside the test, which is allowed for a boundary seam.

Load-bearing against a stub: a body of `return None` (or `return {}` or the identity of an argument)
appends nothing to the log, so the SELECT finds zero rows and every "landed" case below fails. Only a
real call through to honest-observe's frozen emit door, which INSERTs the envelope, lands the row with
the emitted event_type, aggregate_id and JSON payload. The returned Event's own fields are also pinned
to concrete literals, which a `return None` stub cannot satisfy.
"""
import json
import re
import sqlite3

import honest_observe as HO

from honest_alerts import emit

# The one event this test emits: an alert.sent event about one message. These are the literal,
# non-trivial values the law pins -- a concrete event_type, aggregate_type, aggregate_id, payload and
# event_version written out here, not recomputed from the function under test.
_EVENT_TYPE = "alert.sent"
_AGGREGATE_TYPE = "alert"
_AGGREGATE_ID = "msg-7f3c0000-0000-7000-8000-000000000001"
_PAYLOAD = {"message_id": _AGGREGATE_ID, "message_type": "billing.invoice_due", "body_label_id": "lbl-42"}
_CONTEXT = {"auth": {"actor_id": "actor-1"}, "meta": {"trace": "t-1"}}
_EVENT_VERSION = "1"


def _fresh_log_conn():
    """A real in-memory SQLite event log built from honest-observe's event_log_schema() manifest.

    The manifest names the envelope columns and the indexes; it does not fix per-column SQL types
    (honest-observe serializes payload/auth/meta as JSON text and every other column via str()), so the
    columns are created as TEXT, the one shape that stores every envelope cell the frozen emit writes.
    """
    manifest = HO.event_log_schema()
    conn = sqlite3.connect(":memory:")
    table = manifest["table"]
    columns = manifest["columns"]
    column_defs = ", ".join(f"{column} TEXT" for column in columns)
    conn.execute(f"CREATE TABLE {table} ({column_defs})")
    for index in manifest["indexes"]:
        index_columns = ", ".join(index["columns"])
        conn.execute(f"CREATE INDEX {index['name']} ON {table} ({index_columns})")
    conn.commit()
    return conn, table


async def probe_emit():
    """`emit` appends one alert.* event to honest-observe's event log: after the call the row is in the
    log with the emitted event_type, aggregate_id and payload, and the returned Event echoes them."""
    bad = []
    conn, table = _fresh_log_conn()

    returned = await emit(
        _EVENT_TYPE,
        _AGGREGATE_TYPE,
        _AGGREGATE_ID,
        _PAYLOAD,
        _CONTEXT,
        _EVENT_VERSION,
        conn,
    )

    # The effect: exactly one row landed in the event log for this aggregate.
    rows = conn.execute(
        f"SELECT event_type, aggregate_type, aggregate_id, payload, event_version FROM {table} "
        f"WHERE aggregate_id = ?",
        (_AGGREGATE_ID,),
    ).fetchall()

    if len(rows) != 1:
        bad.append(f"emit appended {len(rows)} rows to the event log for {_AGGREGATE_ID!r}, expected 1")
        return bad

    row_event_type, row_aggregate_type, row_aggregate_id, row_payload_text, row_event_version = rows[0]

    # The landed row carries exactly what was emitted.
    landed = [
        ("event_type", row_event_type, _EVENT_TYPE),
        ("aggregate_type", row_aggregate_type, _AGGREGATE_TYPE),
        ("aggregate_id", row_aggregate_id, _AGGREGATE_ID),
        ("event_version", row_event_version, _EVENT_VERSION),
    ]
    for field, got, expect in landed:
        if got != expect:
            bad.append(f"emit landed {field}={got!r} in the log, expected {expect!r}")

    # payload is stored as JSON text; decoded it is the Message that was emitted.
    try:
        row_payload = json.loads(row_payload_text)
    except (TypeError, ValueError) as exc:
        bad.append(f"emit landed a non-JSON payload {row_payload_text!r} ({exc})")
        row_payload = None
    if row_payload != _PAYLOAD:
        bad.append(f"emit landed payload={row_payload!r} in the log, expected {_PAYLOAD!r}")

    # The return is honest-observe's own Event (not a Fault) on a clean append, echoing the seam input.
    if not isinstance(returned, dict):
        bad.append(f"emit returned {returned!r}, expected honest-observe's Event dict on a clean append")
    else:
        if returned.get("event_type") != _EVENT_TYPE:
            bad.append(f"emit returned event_type={returned.get('event_type')!r}, expected {_EVENT_TYPE!r}")
        if returned.get("aggregate_id") != _AGGREGATE_ID:
            bad.append(f"emit returned aggregate_id={returned.get('aggregate_id')!r}, expected {_AGGREGATE_ID!r}")
        if returned.get("payload") != _PAYLOAD:
            bad.append(f"emit returned payload={returned.get('payload')!r}, expected {_PAYLOAD!r}")

    return bad


async def probe_emit_passes_through_a_failed_append():
    """An actual refused insert leaves the log unchanged and returns Observe's Fault."""
    conn, table = _fresh_log_conn()
    try:
        conn.execute(
            f"INSERT INTO {table} (event_type, aggregate_type, aggregate_id) VALUES (?, ?, ?)",
            ("alert.sent", "alert", "previous-message"),
        )
        conn.execute(
            f"CREATE TRIGGER deny_emit BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'Alert law denied append'); END"
        )
        conn.commit()
        before = conn.execute(f"SELECT * FROM {table}").fetchall()
        args = (_EVENT_TYPE, _AGGREGATE_TYPE, _AGGREGATE_ID, _PAYLOAD, _CONTEXT, _EVENT_VERSION, conn)
        actual = await emit(*args)
        after = conn.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        conn.close()

    failures = []
    if not isinstance(actual, dict) or actual.get("is_err") is not True or actual.get("code") != "emit_failed":
        failures.append(f"emit returned {actual!r}, expected Observe's emit_failed Fault")
    else:
        detail = actual.get("detail")
        message = actual.get("message")
        if "Alert law denied append" not in repr(detail):
            failures.append(f"emit did not carry the database write error in the Fault detail: {detail!r}")
        if not isinstance(message, str) or "append" not in message.lower():
            failures.append(f"emit Fault must explain the failed append, got {message!r}")
        elif not any(action in message.lower() for action in ("retry", "check", "restore", "repair", "inspect", "verify", "reconnect", "contact", "try again")):
            failures.append(f"emit Fault must offer a next action, got {message!r}")
    if after != before:
        failures.append(f"failed emit changed the log from {before!r} to {after!r}")
    return failures


async def probe_emit_returns_a_fault_when_the_log_is_missing():
    """A raised append error travels to the caller as a Fault."""
    conn = sqlite3.connect(":memory:")
    try:
        try:
            await HO.emit(_EVENT_TYPE, _AGGREGATE_TYPE, _AGGREGATE_ID, _PAYLOAD, _CONTEXT, _EVENT_VERSION, conn)
        except sqlite3.OperationalError as raised:
            reason = str(raised)
        else:
            return ["fixture did not cause the expected raised SQLite append failure"]
        returned = await emit(
            _EVENT_TYPE,
            _AGGREGATE_TYPE,
            _AGGREGATE_ID,
            _PAYLOAD,
            _CONTEXT,
            _EVENT_VERSION,
            conn,
        )
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()

    failures = []
    if (
        not isinstance(returned, dict)
        or returned.get("is_err") is not True
        or returned.get("category") != "server"
        or returned.get("code") != "emit_seam_failed"
    ):
        failures.append(f"emit returned {returned!r}, expected an emit_seam_failed server Fault for a missing log")
    else:
        detail = returned.get("detail")
        expected = {"aggregate_id": _AGGREGATE_ID, "event_type": _EVENT_TYPE, "detail": reason}
        if detail != expected:
            failures.append(f"emit Fault detail was {detail!r}, expected {expected!r}")
        message = returned.get("message")
        if not isinstance(message, str) or not (
            re.search(r"\b(?:fail\w*|rais\w*|reject\w*|refus\w*|errors?)\b", message, re.I)
            and re.search(
                r"\b(?:not|never|no|nothing|wasn't|didn't)\b[^.;!?]*\b(?:append\w*|record\w*|writ\w*)\b",
                message,
                re.I,
            )
        ):
            failures.append(f"emit Fault must explain the failed append and that no event was written, got {message!r}")
    if tables:
        failures.append(f"emit created unexpected tables on the connection without a log: {tables!r}")
    return failures
