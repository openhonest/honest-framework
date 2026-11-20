"""The emit path: the readers that pull the impure parts, the single write boundary, the orchestrator
that is the one mutator of the event value, and the door the world calls (honest-observe.hd, section
3).

new_event_id reads the random source; event_timestamp reads the clock; next_sequence and append_event
read and write the injected event-log connection conn. run_emit is the single mutator of the event
value: it pulls the three impure parts, extracts the auth and meta partitions, hands them to the pure
build_event, and appends the one envelope through append_event, applying each return into the one
value. emit is the one door the world calls; it delegates to run_emit and returns what it returns.
A fault travels in the return value as a bare union arm (Event | Fault); nothing here raises past the
boundary.
"""

import datetime
import json
import os
import time
import uuid

from honest_type import is_fault

from honest_observe._util import _pick
from honest_observe.events import build_event, extract_auth, extract_meta
from honest_observe.schema import event_log_schema
from honest_observe.types import Event, Fault, WriteOutcome, observe_fault

# The envelope columns that are open maps and so travel to the text log as JSON (section 2.1): the
# payload and the two partitions. A declared, bounded set keyed by column name, so the one append
# serializes each column by its declared shape rather than re-testing a value's runtime type (P14).
_JSON_COLUMNS = frozenset({"payload", "auth", "meta"})


def new_event_id():
    """Pull one fresh event id from the random source: a UUID v7, time-ordered so the log sorts by
    creation without a separate column (section 2.1, 3). It reads random (the UUID v7 random bits) and
    the clock only to order; two reads never return the same value. A reader, not a pure fn, because a
    fresh id is a read of the world."""
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    # UUID v7 layout: 48-bit unix_ms, version 7, 12 random bits, variant, 62 random bits.
    rand_a = rand & 0x0FFF
    rand_b = (rand >> 12) & 0x3FFFFFFFFFFFFFFF
    value = (unix_ms & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0x2 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


def event_timestamp():
    """Pull the current wall-clock time as an ISO-8601 microsecond UTC string, the event's timestamp
    (section 2.1, 3). It reads the clock and nothing else. A reader for the same reason new_event_id
    is: a clock read inside a pure function is the hidden-clock leak the role declaration surfaces."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


async def next_sequence(aggregate_id, conn):
    """Read the event log for the next per-aggregate sequence number, a counter unique and increasing
    within one aggregate_id (section 3.2). It is a pure read of the log itself: the next value is one
    past the highest sequence already appended for this aggregate, so a new aggregate reads 0 and each
    appended event lifts the next read by one. It never writes -- a reader derives the counter from the
    append-only log, it does not keep a separate counter. conn is the injected connection; awaited
    because the read is I/O. run_emit invokes it and applies its answer into the envelope."""
    table = event_log_schema()["table"]
    row = conn.execute(
        f"SELECT COALESCE(MAX(sequence), -1) + 1 FROM {table} WHERE aggregate_id = ?",
        (aggregate_id,),
    ).fetchone()
    return int(row[0])


async def append_event(event, conn):
    """Append one built envelope to the append-only event log through the injected connection and
    report the raw write outcome (section 3). The log is append-only, so this issues no update or
    delete. awaited because the append is I/O. It does ONLY the write: on a clean write it returns a
    WriteOutcome ok true with empty detail, and on a failed write it catches the database exception at
    this boundary and returns a WriteOutcome ok false carrying the error string. It builds no Fault and
    never raises -- a boundary is a terminus, so run_emit reads this outcome and builds the emit_failed
    Fault."""
    manifest = event_log_schema()
    table = manifest["table"]
    columns = manifest["columns"]
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    values = tuple(_to_cell(column, event[column]) for column in columns)
    try:
        conn.execute(f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", values)
        conn.commit()
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True, "detail": ""}


# Serialize one envelope field to a text cell by its declared column kind: a map column (payload, auth,
# meta) as JSON, every other column as its own string form, so the one append writes each column through
# the shape its name declares rather than re-testing the value's runtime type (P14). A lambda, not a def,
# because it is a private serialization helper, the same way honest-auth's _util helpers are lambdas.
_to_cell = lambda column, value: _pick(column in _JSON_COLUMNS, lambda: json.dumps(value), lambda: str(value))


# Turn the WriteOutcome append_event reported into run_emit's return (section 3): the appended Event on
# a clean write, or the emit_failed Fault built via observe_fault on a failed one, naming the retry
# action and carrying the write error for the operator. A closed two-row decision keyed on outcome["ok"],
# not an if ladder (P01); run_emit owns this fault because append_event, a terminus boundary, may not
# call the pure constructor (P24). A lambda, not a def, so it adds no column-0 function to the declared
# set, the same reason honest-auth's _util helpers are lambdas.
_emit_outcome = lambda event, outcome: _pick(
    outcome["ok"],
    lambda: event,
    lambda: observe_fault(
        code="emit_failed",
        message=f"the event-log append failed for event {event.get('event_id')!r}; retry the emit or check the log connection",
        detail={"detail": outcome["detail"]},
    ),
)


async def run_emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn):
    """Run the emit path and be the single mutator of the event value (section 3). It pulls the three
    impure parts -- new_event_id, event_timestamp, next_sequence -- extracts the auth and meta
    partitions from context, and hands them all to build_event, which assembles and validates one
    immutable envelope; no pure function mutates, run_emit applies each return into the one value. On a
    build_event Fault (an empty required field) it returns the Fault without writing; otherwise it
    appends through append_event, reads the WriteOutcome, and returns the event on a clean write or
    builds the emit_failed Fault via observe_fault on a failed one. awaited because next_sequence and
    append_event are I/O."""
    event_id = new_event_id()
    timestamp = event_timestamp()
    sequence = await next_sequence(aggregate_id, conn)
    auth = extract_auth(context)
    meta = extract_meta(context)
    event = build_event(
        event_type,
        event_version,
        aggregate_type,
        aggregate_id,
        payload,
        auth,
        meta,
        event_id,
        timestamp,
        sequence,
    )

    async def _return_fault():
        # build_event faulted on an empty required field: return the Fault without writing, so the
        # fault bubbles to the door by return and nothing reaches the log (section 3).
        return event

    async def _append_and_decide():
        # build_event produced an Event: append it through the one write boundary, read the
        # WriteOutcome, and return the Event or the emit_failed Fault run_emit builds from the outcome.
        outcome = await append_event(event, conn)
        return _emit_outcome(event, outcome)

    chosen = _pick(is_fault(event), _return_fault, _append_and_decide)
    return await chosen


async def emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn):
    """The one door that writes an event to the log, called from inside an application chain link
    declared at the boundary (section 3, 3.1). The world calls in here and nothing inside the module
    calls it; it hands its input to run_emit and returns what run_emit returns -- the appended Event or
    a Fault. awaited because run_emit is. It returns Event | Fault rather than raising, because the
    calling link decides whether a failed emit stops its chain."""
    return await run_emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn)
