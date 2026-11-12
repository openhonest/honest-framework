"""The event-log boundaries honest-observe owns (section 3).

Each touches one side of the world and nothing else. new_event_id draws from the random source.
event_timestamp reads the clock. next_sequence reads the event log in honest-persist for the count
of an aggregate's events, and append_event writes one event to it; both carry the log connection in
as a handle. run_emit is handed these four so a test substitutes a stand-in for each, and the real
ones live here because honest-observe owns what it touches.
"""

import uuid
from datetime import datetime, timezone

import honest_persist
from honest_type import link


@link(boundary=True)
def new_event_id():
    """A fresh event id, from the random source."""
    return uuid.uuid4().hex


@link(boundary=True)
def event_timestamp():
    """The current instant as an ISO-8601 string, from the clock."""
    return datetime.now(timezone.utc).isoformat()


@link(boundary=True)
async def next_sequence(aggregate_id, conn):
    """The next per-aggregate sequence number: the count of that aggregate's events in the log."""
    rows = await honest_persist.execute(honest_persist.select("events", ["event_id"], {"aggregate_id": aggregate_id}), conn)
    return len(rows)


@link(boundary=True)
async def append_event(event, conn):
    """Append one event to the log, in one transaction."""
    return await honest_persist.transaction([honest_persist.insert("events", event)], conn)
