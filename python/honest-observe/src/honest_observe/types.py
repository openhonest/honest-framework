"""honest-observe data dictionary: the event-log envelope, the projection and metric handles, the
absence sentinel, and the single place a fault is built (honest-observe.hd types; sections 2, 3, 6,
8b, 8c).

honest-observe owns five record shapes -- Event, Projection, Metric, ThresholdProjection, Fault -- and
no class: each is a TypedDict, data with no behaviour attached. A Fault is a bare union arm (value | Fault), recognized by
honest-type's is_fault off the reserved is_err tag, never raised and never wrapped in an ok/err
envelope (honest-errors-architecture.md section 2, 3). observe_fault is the one constructor that
assembles one, so is_err is set in exactly one place.
"""

from typing import Any, TypedDict

# The empty tuple is the bounded absence resolve_identity yields when an external id binds to no
# canonical id (section 8c.3). It carries no is_err tag, so honest-type's is_fault never recognizes
# it, keeping the absence disjoint from a Fault; and it is immutable, so a shared NOTHING can never be
# mutated into something else. resolve_identity returns str | NOTHING, never a Fault.
NOTHING = ()


class Event(TypedDict):
    """One event-log envelope, the single shape every event takes (section 2.1). event_id is the
    UUID v7; event_type is the dot-namespaced identifier; event_version is the schema version as a
    str; timestamp is ISO-8601 microsecond UTC; sequence is per-aggregate and increasing;
    aggregate_type and aggregate_id say what thing the event is about and which one; payload is the
    event-type-specific open map; auth is the auth partition carried verbatim; meta is the optional
    application metadata."""

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


class Projection(TypedDict):
    """A declared named projection: the id it is registered under and the event types it folds over
    (section 6). It carries no fold or initial_state field: those are callables the pure folds take
    as arguments, kept out of the stored handle so the handle stays flat and serializable."""

    projection_id: str
    event_types: list[str]


class Metric(TypedDict):
    """A built-in or custom metric handle: its name and the event types it is computed from (section
    8b.3, 8b.5). It names no fold, value or group function: those are callables passed to
    compute_metric, not stored in the flat handle."""

    name: str
    event_types: list[str]


class ThresholdProjection(TypedDict):
    """A threshold projection: a projection that watches a metric and fires an alert when a declared
    condition is crossed (section 8b.1, 8b.2). Richer than Projection, which is why threshold_projection
    returns this and not that: projection_id is its unique id; metric is the NAME of the watched metric
    (the live Metric handle is passed to evaluate_threshold separately, so the threshold stores only the
    name); condition is the comparison that fires it ({operator: bound}); window is the time window the
    metric is computed over; cooldown is the minimum time between firings; alert is the message,
    recipient and surface to send; enabled lets an operator toggle it without redeployment. It is a
    honest-persist record, so it is flat and serializable."""

    projection_id: str
    metric: str
    condition: Any
    window: str
    cooldown: str
    alert: Any
    enabled: bool


class Fault(TypedDict):
    """The failure an observe function returns as a bare union arm (value | Fault), recognized by
    honest-type's is_fault and never raised and never wrapped in an ok/err envelope. is_err is the
    reserved boolean tag, always true, the mark is_fault reads to tell the fault arm from the value
    arm. code is the specific reason (emit_failed, empty_required_field). message is the human
    sentence naming what went wrong and what to do instead. detail is the structured context."""

    is_err: bool
    code: str
    message: str
    detail: dict[str, Any]


class WriteOutcome(TypedDict):
    """The raw outcome append_event reports for one log write (section 3). It is not a Fault and not
    the ok/err envelope: it is a boundary's plain report of what the database did, so the terminus
    boundary stays a thin write and leaves fault construction to run_emit. ok is true on a clean write
    and false on a failed one; detail is empty on success and carries the write error on failure,
    which run_emit passes into the emit_failed Fault it builds via observe_fault."""

    ok: bool
    detail: str


def observe_fault(code: str, message: str, detail: dict) -> Fault:
    """Build one observe Fault record from its parts -- the single place honest-observe assembles a
    fault. It sets is_err true and returns the Fault, carried by the return as a bare union arm and
    recognized by is_fault, never raised and never wrapped in an envelope. Pure: it reads no world."""
    return {"is_err": True, "code": code, "message": message, "detail": detail}
