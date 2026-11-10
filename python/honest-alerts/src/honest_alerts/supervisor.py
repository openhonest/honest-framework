"""The supervisor's pure core and the delivery pass (section 6).

Matching a message to routes and planning one delivery per channel are pure (sections 6.1). The
delivery pass, run_deliveries, is the orchestrator the worker runs: it reads the pending records,
dispatches each on its channel through the handler table, records the outcome, and emits the event.
Every side of the world it touches is a boundary handed in, so a test drives it with stand-ins; the
real boundaries live in honest_alerts.boundaries, and the handler table names one per channel.
"""

from honest_type import ok

from honest_alerts import boundaries
from honest_alerts.events import alert_event


def message_type_matches(pattern, message_type):
    """Whether a route's message_type pattern matches a message's type (sections 5.1, 6.1). A pattern
    ending in '.*' matches any type in that namespace; otherwise the match is exact. Pure."""
    if pattern.endswith(".*"):
        return message_type.startswith(pattern[:-1])
    return pattern == message_type


def matching_routes(routing_table, message):
    """The routes that handle a message, priority ascending (section 6.1): the message type matches the
    route's pattern, and the route's sender_type, when set, equals the message sender's type. Pure."""
    matches = [
        route
        for route in routing_table
        if message_type_matches(route["message_type"], message["message_type"])
        and (route.get("sender_type") is None or route["sender_type"] == message["sender"]["type"])
    ]
    return sorted(matches, key=lambda route: route["priority"])


def delivery_plan(message, routes, now):
    """One pending delivery record per channel across the matched routes (section 6.1): the recipient is
    the channel's recipient_spec or the message's recipient, the endpoint is the channel's configured
    one, and deliver_at is now plus the channel's delay. Pure — now is injected, not read."""
    return [
        {
            "message_id": message["message_id"],
            "route_id": route["route_id"],
            "channel": channel_config["channel"],
            "recipient": channel_config.get("recipient_spec") or message["recipient"],
            "endpoint": channel_config.get("endpoint", ""),
            "deliver_at": now + channel_config.get("delay_seconds", 0),
            "status": "pending",
        }
        for route in routes
        for channel_config in route["channels"]
    ]


# One delivery handler per channel (section 6.2): the dispatch table run_deliveries picks from, a
# table and not a branch. The keys are exactly the declared CHANNELS.
DELIVER_BY_CHANNEL = {
    "dom": boundaries.deliver_dom,
    "email": boundaries.deliver_posted,
    "sms": boundaries.deliver_posted,
    "webhook": boundaries.deliver_posted,
    "slack": boundaries.deliver_posted,
    "teams": boundaries.deliver_posted,
}


async def run_deliveries(conn, transport, read_pending, deliver_by_channel, mark_delivery, emit_event):
    """Dispatch every due pending delivery through its channel and record the outcome (section 6.2): a
    success marks the record delivered and emits alert.delivered; a failure marks it failed and emits
    alert.delivery_failed. Returns ok({executed}). I/O only through the handed-in boundaries: conn for
    the queue and the log, transport for the channels."""
    pending = await read_pending(conn)
    for delivery in pending:
        handler = deliver_by_channel[delivery["channel"]]
        result = await handler(delivery, conn, transport)
        if "ok" in result:
            await mark_delivery(delivery, "delivered", conn)
            await emit_event(alert_event("alert.delivered", delivery["message_id"], delivery), conn)
        else:
            await mark_delivery(delivery, "failed", conn)
            await emit_event(alert_event("alert.delivery_failed", delivery["message_id"], delivery), conn)
    return ok({"executed": len(pending)})


async def tick(conn, transport):
    """The door the delivery worker calls (section 6.2): run one delivery pass with the module's own
    boundaries and the real channel-handler table. conn is the honest-persist connection, transport the
    channel transport, both handed in by the worker."""
    return await run_deliveries(conn, transport, boundaries.read_pending, DELIVER_BY_CHANNEL, boundaries.mark_delivery, boundaries.emit_event)
