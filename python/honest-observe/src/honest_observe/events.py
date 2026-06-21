"""The event envelope (section 2): every event in the log shares one shape.

An event is plain data — a dict with framework fields, an open `payload`, an `auth` partition
owned by the auth layer, and optional `meta`. `build_event` assembles a validated envelope and
is **pure**: the three impure fields (`event_id`, `timestamp`, `sequence`) are generated at the
emit boundary and passed in, so assembly itself reads nothing from the outside world. A missing
required field is a fault as data, never an exception.

`extract_auth` / `extract_meta` pull the auth and meta partitions out of a request context by
the configured field names (section 2.2, 2.3). The framework never interprets `auth.*` — it only
carries it forward.
"""

from typing import Any, TypedDict

from honest_type import err, fault, ok


class Event(TypedDict, total=False):
    event_id: str
    event_type: str
    event_version: str
    timestamp: str
    sequence: int
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    auth: dict[str, Any]
    meta: dict[str, Any]


# Fields an event cannot be valid without — non-empty strings, all of them. `sequence` (which
# may legitimately be 0) and `payload` (which may be empty) are deliberately not in this set.
_REQUIRED = ("event_id", "event_type", "event_version", "timestamp", "aggregate_type", "aggregate_id")


def build_event(event_type, event_version, aggregate_type, aggregate_id, payload, event_id, timestamp, sequence, auth=None, meta=None):
    """Assemble a validated event envelope (section 2). Pure. Returns ok(Event), or
    err(fault 'invalid_event') listing any required field left empty. `auth`/`meta` are attached
    only when supplied (a no-auth event omits the key, section 2.2)."""
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": event_version,
        "timestamp": timestamp,
        "sequence": sequence,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "payload": payload,
    }
    if auth is not None:
        event["auth"] = auth
    if meta is not None:
        event["meta"] = meta
    missing = [name for name in _REQUIRED if not event[name]]
    if missing:
        return err(fault("invalid_event", f"Event is missing required field(s): {missing}", "server", {"missing": missing}))
    return ok(event)


def extract_auth(context, auth_fields):
    """The auth partition for an event (section 2.2): the configured `auth_fields` present in the
    request context, in order. None when no field is present (a no-auth event). Pure."""
    auth = {name: context[name] for name in auth_fields if name in context}
    return auth or None


def extract_meta(context, meta_fields):
    """The meta partition for an event (section 2.3): the configured `meta_fields` present in the
    request context, in order. None when no field is present. Pure."""
    meta = {name: context[name] for name in meta_fields if name in context}
    return meta or None
