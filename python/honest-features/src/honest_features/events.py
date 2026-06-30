"""The two honest-observe events honest-features emits (section 8).

honest-features builds the event payloads as pure values; honest-observe owns the log. The change event
records a successful toggle; the evaluation event records a flag read in request context.
"""


def changed_event(flag, previous, state, timestamp, requesting_ip):
    """The hf.features.changed event, emitted after a successful toggle (section 8.1). Pure."""
    return {
        "event_type": "hf.features.changed",
        "flag": flag,
        "previous": previous,
        "state": state,
        "timestamp": timestamp,
        "requesting_ip": requesting_ip,
    }


def evaluated_event(flag, state, request_id):
    """The hf.features.evaluated event, emitted when a flag is read in request context (section 8.2). Pure."""
    return {"event_type": "hf.features.evaluated", "flag": flag, "state": state, "request_id": request_id}
