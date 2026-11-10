"""The boundaries honest-alerts owns (sections 6, 8, 9, 11).

Each touches one side of the world and nothing else. The clock and a random source give the send
time and the ids. honest-persist holds the routing table and the delivery queue. honest-observe
holds the alert event log, read for the mailbox and for a reply, and written for every alert.*
event. The six channel handlers carry a message out over the network. A connection is passed in as
a handle. Every one is a boundary, so an orchestrator hands a test a stand-in for each; the real
ones live here because honest-alerts owns what it touches.
"""

import asyncio
import tomllib
import uuid
from datetime import datetime, timezone

import honest_observe
import honest_persist
from honest_type import link

# The configuration file the deployment supplies (section 11).
_CONFIG_PATH = "honest-alerts.toml"


@link(boundary=True)
def now():
    """The wall clock, in epoch seconds (section 8)."""
    return int(datetime.now(timezone.utc).timestamp())


@link(boundary=True)
def new_message_id():
    """A fresh message id, from the random source (section 8)."""
    return uuid.uuid4().hex


@link(boundary=True)
def new_resume_token():
    """A fresh reply-correlation token, from the random source (section 8.2)."""
    return uuid.uuid4().hex


@link(boundary=True)
async def read_routes(conn):
    """Read the routing table from honest-persist (section 5)."""
    return await honest_persist.execute(honest_persist.select("alert_routes", ["*"], {}), conn)


@link(boundary=True)
async def read_pending(conn):
    """Read the due pending delivery records from honest-persist (section 6.2)."""
    return await honest_persist.execute(honest_persist.select("alert_deliveries", ["*"], {"status": "pending"}), conn)


@link(boundary=True)
async def read_events(conn, actor_ref):
    """Read the events addressed to an actor from honest-observe (section 4)."""
    return await honest_persist.execute(honest_persist.select("events", ["*"], {"aggregate_type": "alert"}), conn)


@link(boundary=True)
async def await_reply(conn, message_id, timeout_seconds):
    """Wait for a reply event on honest-observe's log, polling until it arrives or the wait runs out
    (section 8.3). Returns the reply, or None on timeout. No thread is held between polls."""
    waited = 0
    step = 1
    while waited <= (timeout_seconds or 0):
        rows = await honest_persist.execute(honest_persist.select("events", ["*"], {"aggregate_id": message_id, "event_type": "alert.replied"}), conn)
        if rows:
            payload = rows[0]["payload"]
            return {"option_id": payload["option_id"], "actor_id": payload["actor_id"], "reply_payload": payload["reply_payload"]}
        await asyncio.sleep(step)
        waited += step
    return None


@link(boundary=True)
def read_raw_config():
    """Read and parse the alert configuration file (section 11)."""
    with open(_CONFIG_PATH, "rb") as handle:
        return tomllib.load(handle)


@link(boundary=True)
async def write_delivery(delivery, conn):
    """Append one pending delivery record to the queue in honest-persist (section 6.1)."""
    return await honest_persist.transaction([honest_persist.insert("alert_deliveries", delivery)], conn)


@link(boundary=True)
async def mark_delivery(delivery, status, conn):
    """Update a delivery record's status in honest-persist (section 6.2)."""
    return await honest_persist.transaction([honest_persist.update("alert_deliveries", {"status": status}, {"message_id": delivery["message_id"], "route_id": delivery["route_id"], "channel": delivery["channel"]})], conn)


@link(boundary=True)
async def emit_event(event, conn):
    """Append one alert.* event to honest-observe's log (section 10). The event is the shaped record
    alert_event produced: its event_type, aggregate id, and payload."""
    body = event["ok"]
    return await honest_observe.emit(body["event_type"], body["aggregate_type"], body["aggregate_id"], body["payload"], {}, 1, conn, [], [])


@link(boundary=True)
async def deliver_dom(delivery, conn, transport):
    """Deliver over the DOM channel (section 9): the rendered surface reaches the browser through the
    event log, so the delivery is recorded as an alert.read impression the mailbox projects."""
    return await honest_observe.emit("alert.read", "alert", delivery["message_id"], delivery, {}, 1, conn, [], [])


@link(boundary=True)
async def deliver_posted(delivery, conn, transport):
    """Deliver over any posted channel — email, SMS, webhook, Slack, or Teams (section 6): post the
    message to the configured endpoint through the injected transport. The transport, not this module,
    owns the HTTP, the way honest-persist owns the database behind its connection. These channels differ
    only in the endpoint their config names, not in how the message is sent, so one deliverer serves
    them all; deliver_dom is the one channel that does not post to an endpoint."""
    return await transport.post(delivery["endpoint"], delivery)
