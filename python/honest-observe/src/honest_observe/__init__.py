"""honest-observe - event-sourced observability.

One append-only event log; projections are pure folds over it. Implemented: the event envelope
(section 2), the emit boundary (section 3), and projections (section 6). emit reaches the outside
world — id, clock, sequence, and the log writer — only through an injected runtime, so observe is
stored by persist without importing it. The log storage itself is the runtime's concern.
"""

from honest_observe.browser import browser_classify, browser_request, browser_response, build_browser_event, dom_changed
from honest_observe.devtools import format_tail_line
from honest_observe.emit import emit
from honest_observe.event_log import event_log_manifest, event_log_schema
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
from honest_observe.otel import otel_attributes, otel_signal, otel_signal_kind
from honest_observe.projections import apply_projection, matches
from honest_observe.snapshot import build_snapshot, declare_projection, resume_from_snapshot, should_snapshot

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
    "event_log_schema",
    "event_log_manifest",
    "build_snapshot",
    "should_snapshot",
    "declare_projection",
    "resume_from_snapshot",
    "otel_signal_kind",
    "otel_attributes",
    "otel_signal",
    "build_browser_event",
    "browser_classify",
    "browser_request",
    "browser_response",
    "dom_changed",
    "format_tail_line",
]
