"""The supervisor (section 6): turn a message and the routing table into deliveries and events.

The supervisor is table-driven and stateless. Its decision is pure: match the message to routes
(section 6.1), sort by priority, and build one delivery record per channel. The two boundaries,
supervise and execute_deliveries, reach the outside world — the delivery queue, the event log, and the
channel handlers — only through an injected `runtime`, never a global, a clock, or an import. That keeps
honest-alerts free of honest-persist and honest-observe imports and leaves the actual I/O to the runtime
the application supplies (mirroring honest-observe's emit).

The runtime the boundaries expect:
  now()                          -> epoch seconds
  await insert(delivery)         -> Result   (append to the alert_deliveries queue)
  await emit(type, agg_id, body) -> Result   (append an alert.* event to the log)
  await pending()                -> [delivery]  (due, pending delivery records)
  await deliver(delivery)        -> Result   (dispatch through the channel handler)
  await mark(delivery, status)   -> Result   (update the delivery record's status)
"""

from honest_type import ok


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
    the channel's recipient_spec or the message's recipient, and deliver_at is now plus the channel's
    delay. Pure — now is injected, not read."""
    return [
        {
            "message_id": message["message_id"],
            "route_id": route["route_id"],
            "channel": channel_config["channel"],
            "recipient": channel_config.get("recipient_spec") or message["recipient"],
            "deliver_at": now + channel_config.get("delay_seconds", 0),
            "status": "pending",
        }
        for route in routes
        for channel_config in route["channels"]
    ]


async def supervise(message, routing_table, runtime):
    """Route a message: write a pending delivery per channel and emit alert.sent; if no route matches,
    emit an alert.no_route warning and deliver nothing (section 6.1). Returns ok({delivered}). I/O only
    through the injected runtime."""
    routes = matching_routes(routing_table, message)
    if not routes:
        await runtime.emit("alert.no_route", message["message_id"], {"message_type": message["message_type"]})
        return ok({"delivered": 0})
    plan = delivery_plan(message, routes, runtime.now())
    for delivery in plan:
        await runtime.insert(delivery)
    await runtime.emit("alert.sent", message["message_id"], message)
    return ok({"delivered": len(plan)})


async def execute_deliveries(runtime):
    """Dispatch every due pending delivery through its channel and record the outcome (section 6.2): a
    success marks the record delivered and emits alert.delivered; a failure marks it failed and emits
    alert.delivery_failed. Returns ok({executed}). I/O only through the injected runtime."""
    pending = await runtime.pending()
    for delivery in pending:
        result = await runtime.deliver(delivery)
        if "ok" in result:
            await runtime.mark(delivery, "delivered")
            await runtime.emit("alert.delivered", delivery["message_id"], delivery)
        else:
            await runtime.mark(delivery, "failed")
            await runtime.emit("alert.delivery_failed", delivery["message_id"], delivery)
    return ok({"executed": len(pending)})
