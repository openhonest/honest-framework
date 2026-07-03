"""The mailbox projection and message termination (section 4).

A mailbox is not a data structure; it is a projection over honest-observe's event log — the answer to
"which messages addressed to me have not yet terminated?". These functions are pure: they take the
events as data and never read the log, so they are exhaustively testable. The boundary that pulls
events from the log formats timestamps; here time is epoch seconds, so ttl arithmetic is ordinary
subtraction (the spec's §3.1 `sent_at` is the boundary's ISO serialization of the same instant).

A message ends by exactly one of four conditions, and an acknowledged message ends when its scope is
satisfied. Both selections go through a table, never an if/elif chain: the condition names the
predicate; the ack_scope names the predicate.
"""


def recipient_matches(recipient, actor_ref):
    """Whether a message's recipient addresses `actor_ref` (section 4.1). Pure. The type must match; a
    recipient `id` of None broadcasts to every actor of that type; a set `id` must equal the actor's id;
    a recipient `tenant_id`, when present, must equal the actor's. Independent guards, not a discriminant."""
    if recipient["type"] != actor_ref["type"]:
        return False
    if recipient.get("id") is not None and recipient["id"] != actor_ref.get("id"):
        return False
    if recipient.get("tenant_id") is not None and recipient["tenant_id"] != actor_ref.get("tenant_id"):
        return False
    return True


def _terminated_ttl(event, actor_ref, events, at_time):
    """A ttl message ends `ttl_seconds` after it was sent (section 3.3, 4.1). The edge is inclusive:
    at exactly sent_at + ttl_seconds the message is still live."""
    message = event["payload"]
    return at_time > message["sent_at"] + message["termination"]["ttl_seconds"]


def _acknowledged_session(acks, actor_ref):
    """Session scope: acknowledged when this DOM session has an ack (section 3.4, 4.1)."""
    return any(ack["payload"].get("session_id") == actor_ref.get("session_id") for ack in acks)


def _acknowledged_actor(acks, actor_ref):
    """Actor scope: acknowledged when the recipient actor has an ack on any session (section 3.4, 4.1)."""
    return any(ack["payload"].get("actor_id") == actor_ref.get("id") for ack in acks)


def _acknowledged_broadcast(acks, actor_ref):
    """Broadcast scope: acknowledged when any one recipient has acked (section 3.4, 4.1)."""
    return len(acks) > 0


_ACK_SCOPE = {
    "session": _acknowledged_session,
    "actor": _acknowledged_actor,
    "broadcast": _acknowledged_broadcast,
}


def _terminated_acknowledged(event, actor_ref, events, at_time):
    """An acknowledged message ends when its ack_scope is satisfied by alert.acknowledged events for it
    (section 4.1). The scope selects the predicate through `_ACK_SCOPE`, not an if/elif chain."""
    message = event["payload"]
    acks = [e for e in events if e["event_type"] == "alert.acknowledged" and e["payload"]["message_id"] == message["message_id"]]
    return _ACK_SCOPE[message["ack_scope"]](acks, actor_ref)


def _event_filter_matches(event, event_filter):
    """Whether an event's payload satisfies an optional termination event_filter (section 4.1). A None
    filter matches unconditionally; otherwise every filter key must equal the payload's value."""
    if event_filter is None:
        return True
    return all(event["payload"].get(key) == value for key, value in event_filter.items())


def _terminated_event(event, actor_ref, events, at_time):
    """An event-terminated message ends when a matching terminating event is appended at or after the
    message was sent (section 3.3, 4.1)."""
    message = event["payload"]
    spec = message["termination"]
    terminating = [
        e
        for e in events
        if e["event_type"] == spec["event_type"]
        and e["timestamp"] >= message["sent_at"]
        and _event_filter_matches(e, spec.get("event_filter"))
    ]
    return len(terminating) > 0


def _terminated_never(event, actor_ref, events, at_time):
    """A never-terminated message persists until explicitly deleted (section 3.3, 4.1)."""
    return False


_TERMINATION = {
    "ttl": _terminated_ttl,
    "acknowledged": _terminated_acknowledged,
    "event": _terminated_event,
    "never": _terminated_never,
}

TERMINATION_CONDITIONS = frozenset(_TERMINATION)
ACK_SCOPES = frozenset(_ACK_SCOPE)


def is_terminated(event, actor_ref, events, at_time):
    """Whether an alert.sent event's message has terminated for `actor_ref` at `at_time` (section 4.1).
    Pure: the condition selects a predicate through `_TERMINATION`; acks and terminating events are read
    from the given `events` list, never the log."""
    return _TERMINATION[event["payload"]["termination"]["condition"]](event, actor_ref, events, at_time)


def mailbox(actor_ref, events, at_time):
    """The actor's pending messages at `at_time` (section 4.1): the alert.sent events addressed to it and
    not yet terminated, oldest first. Pure projection over the given events."""
    sent = [
        e
        for e in events
        if e["event_type"] == "alert.sent"
        and recipient_matches(e["payload"]["recipient"], actor_ref)
        and e["payload"]["sent_at"] <= at_time
    ]
    pending = [e for e in sent if not is_terminated(e, actor_ref, events, at_time)]
    return sorted(pending, key=lambda e: e["payload"]["sent_at"])
