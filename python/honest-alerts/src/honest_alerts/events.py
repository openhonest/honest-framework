"""The honest-observe event catalog (section 10).

Every honest-alerts event flows through honest-observe under one aggregate type, "alert". ALERT_EVENTS
is the complete catalog: each event type and when it fires. It is the single registry projections,
dashboards, and trigger rules read, and the consistency law pins it to cover every event the module's
boundaries and lifecycle transitions produce.

alert_event shapes a cataloged event for observe: it rejects an uncataloged event type (a programming
error, so a server fault) and otherwise returns the event_type, the alert aggregate, the message id as
the aggregate id, and the payload — the arguments observe.emit records.
"""

from honest_type import err, fault, ok

ALERT_AGGREGATE = "alert"

# The complete alert event set and when each fires (section 10). alert.no_route is the routing warning
# the supervisor emits (section 6.1); read/actioned/escalated/expired/failed are cataloged here and
# emitted by the DOM actor and the escalation and expiry pollers.
ALERT_EVENTS = {
    "alert.sent": "Message created and queued for delivery",
    "alert.no_route": "No route matched the message type; the message was not delivered (a warning)",
    "alert.delivered": "Successfully delivered via a channel",
    "alert.delivery_failed": "Channel delivery failed",
    "alert.read": "DOM actor rendered the message (impression)",
    "alert.replied": "Recipient chose a reply option",
    "alert.acknowledged": "Message acknowledged (scope met)",
    "alert.actioned": "Message actioned (non-acknowledge response)",
    "alert.escalated": "Escalated due to TTL with no acknowledgment",
    "alert.expired": "TTL reached with no acknowledgment",
    "alert.failed": "Delivery failed across all channels",
}


def alert_event(event_type, aggregate_id, payload):
    """Shape a cataloged alert event for honest-observe (section 10). Returns ok with the observe emit
    arguments (event_type, the alert aggregate, the message id, the payload), or a server fault if the
    event type is not in the catalog. Pure."""
    if event_type not in ALERT_EVENTS:
        return err(fault("unknown_alert_event", f"'{event_type}' is not a declared alert event", "server", detail=event_type))
    return ok({"event_type": event_type, "aggregate_type": ALERT_AGGREGATE, "aggregate_id": aggregate_id, "payload": payload})
