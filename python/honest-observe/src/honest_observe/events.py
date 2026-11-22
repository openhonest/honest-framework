"""Pure event-shaping functions: pull the auth and meta partitions out of the manifest, and build one
immutable event envelope from its already-computed parts (honest-observe.hd, sections 2, 3).

build_event is the one place the envelope is built and validated, so the event shape is stated once.
Validation is a fault as data, not an exception: an empty required field returns the Fault arm, never
raises. extract_auth and extract_meta copy a block verbatim and inspect no field.
"""

from honest_observe._util import _get, _pick
from honest_observe.types import Event, Fault, observe_fault

# The context partition keys: auth is carried verbatim and never read by the framework for anything
# but attaching it; meta is the optional application metadata (section 2.2, 2.3). Named here so the
# one place the partition boundary is decided is the one place these keys are written.
_AUTH_KEY = "auth"
_META_KEY = "meta"

# The envelope's required string fields: the identity and provenance of the event, each of which
# names what the event is and which one, so an empty one leaves the envelope unidentifiable (section
# 2.1). payload, auth and meta are open maps that may legitimately be empty, so they are not required
# to be non-empty; sequence is an int the orchestrator assigns, not an emptiable string.
_REQUIRED_STRING_FIELDS = (
    "event_type",
    "event_version",
    "aggregate_type",
    "aggregate_id",
    "event_id",
    "timestamp",
)


def extract_auth(context):
    """Pull the auth partition out of the current manifest at the context's auth key, copied verbatim
    for attachment to the envelope, returning the empty dict when absent (section 2.2). Pure: a map
    read, no world, no fault."""
    return _get(context, _AUTH_KEY, {})


def extract_meta(context):
    """Pull the optional application-metadata partition out of the current manifest at the context's
    meta key, carried verbatim, returning the empty dict when absent (section 2.3). Pure: a map read,
    no world, no fault."""
    return _get(context, _META_KEY, {})


def build_event(event_type, event_version, aggregate_type, aggregate_id, payload, auth, meta, event_id, timestamp, sequence):
    """Assemble one immutable Event envelope from its already-computed parts and validate it, returning
    the Event or a Fault with code empty_required_field when a required string field is empty (section
    2, 3). The impure parts -- event_id, timestamp, sequence -- and the extracted auth and meta are
    passed in, so this is a pure constructor that runs without a clock, a random source or a database.
    An empty required field returns the Fault arm, never raises."""
    envelope: Event = {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": event_version,
        "timestamp": timestamp,
        "sequence": sequence,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "payload": payload,
        "auth": auth,
        "meta": meta,
    }
    empty = list(filter(lambda field: envelope[field] == "", _REQUIRED_STRING_FIELDS))
    return _pick(
        not empty,
        lambda: envelope,
        lambda: observe_fault(
            code="empty_required_field",
            message=f"the event envelope's required fields {empty} were empty; emit must supply a non-empty value for each so the event is identifiable in the log",
            detail={"fields": empty},
        ),
    )
