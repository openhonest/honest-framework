"""honest-observe — append-only event log + projections + external ingestion.

Three layers, one log: browser beacons, framework middleware, external
webhooks. All canonicalised into the same Event envelope. Projections
fold the log into derived read models on demand.
"""
from honest_observe.events import (
    advance_hlc,
    build_envelope,
    extract_auth,
    extract_meta,
    fold,
    map_event_to_otel,
    next_sequence,
    project,
    recognize_stripe_payment,
    reject_event,
    resolve_identity,
    translate_generic_webhook,
    translate_stripe_payment,
)
from honest_observe.log import (
    append_event,
    append_rejection,
    export_otel,
    read_event_log,
    read_rejections,
    read_snapshot,
    reset_log,
    stream_tail,
    write_snapshot,
)
from honest_observe.orchestrator import emit, run_projection
from honest_observe.types import (
    AuthPartition,
    EmitResult,
    Event,
    EventMeta,
    HLC,
    Projection,
    Rejection,
    Snapshot,
)

__all__ = [
    "AuthPartition",
    "EmitResult",
    "Event",
    "EventMeta",
    "HLC",
    "Projection",
    "Rejection",
    "Snapshot",
    "advance_hlc",
    "append_event",
    "append_rejection",
    "build_envelope",
    "emit",
    "export_otel",
    "extract_auth",
    "extract_meta",
    "fold",
    "map_event_to_otel",
    "next_sequence",
    "project",
    "read_event_log",
    "read_rejections",
    "read_snapshot",
    "recognize_stripe_payment",
    "reject_event",
    "reset_log",
    "resolve_identity",
    "run_projection",
    "stream_tail",
    "translate_generic_webhook",
    "translate_stripe_payment",
    "write_snapshot",
]
