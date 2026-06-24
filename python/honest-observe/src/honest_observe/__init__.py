"""honest-observe - event-sourced observability.

One append-only event log; projections are pure folds over it. Implemented: the event envelope
(section 2), the emit boundary (section 3), and projections (section 6). emit reaches the outside
world — id, clock, sequence, and the log writer — only through an injected runtime, so observe is
stored by persist without importing it. The log storage itself is the runtime's concern.
"""

from honest_observe.emit import emit
from honest_observe.events import Event, build_event, extract_auth, extract_meta
from honest_observe.framework_events import (
    app_error,
    app_started,
    app_stopped,
    chain_completed,
    chain_started,
    classify_completed,
    link_executed,
    link_faulted,
    link_summary,
    request_canonical,
    state_rejected,
    state_transitioned,
)
from honest_observe.projections import apply_projection, matches

__all__ = [
    "Event",
    "build_event",
    "extract_auth",
    "extract_meta",
    "emit",
    "apply_projection",
    "matches",
    "chain_started",
    "chain_completed",
    "link_executed",
    "link_faulted",
    "classify_completed",
    "state_transitioned",
    "state_rejected",
    "link_summary",
    "request_canonical",
    "app_started",
    "app_stopped",
    "app_error",
]
