"""honest-observe - event-sourced observability (core unit): one append-only event log written by one
emit boundary and read back only through pure projections (honest-observe.hd, section 1).

__all__ is the public import surface -- the functions the declaration gives an import or call entry.
The internal emit-path and pure helpers (run_emit, the readers, the write boundary, the partition
extractors, build_event, matches) are importable module attributes the laws and value map reference,
but are not part of the public surface, so they are left out of __all__.
"""

from honest_observe.types import NOTHING, Event, Fault, Metric, Projection, observe_fault
from honest_observe.events import build_event, extract_auth, extract_meta
from honest_observe.emit import (
    append_event,
    emit,
    event_timestamp,
    new_event_id,
    next_sequence,
    run_emit,
)
from honest_observe.schema import event_log_schema
from honest_observe.canonical import request_canonical
from honest_observe.projections import (
    apply_projection,
    build_snapshot,
    declare_projection,
    matches,
    resume_from_snapshot,
)
from honest_observe.otel import otel_signal
from honest_observe.thresholds import compute_metric, evaluate_threshold, threshold_projection
from honest_observe.hlc import hlc_receive, hlc_send
from honest_observe.identity import fold_identity_claims, resolve_identity

__all__ = [
    "emit",
    "request_canonical",
    "apply_projection",
    "declare_projection",
    "build_snapshot",
    "resume_from_snapshot",
    "otel_signal",
    "compute_metric",
    "threshold_projection",
    "evaluate_threshold",
    "hlc_send",
    "hlc_receive",
    "fold_identity_claims",
    "resolve_identity",
    "event_log_schema",
]
