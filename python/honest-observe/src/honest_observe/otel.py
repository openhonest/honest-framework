"""Projects one event to its OpenTelemetry signal as pure data, the signal kind following the event
type as a mapping read from the event, not a branch ladder (honest-observe.hd otel_signal, section 7).

The signal kind is chosen from a declared mapping of event-type suffix to OTel signal kind -- a table,
not an if/elif ladder (P01). The kinds are a bounded set {span_start, child_span, db_span, metric,
span_event}; span_event is the explicit terminal kind for any event-type suffix the table does not
name, a named case the mapping declares rather than a silent default shaped like a hit (P16): every
event is observable, so an unlisted type is not a program bug but an ordinary span event. The signal
carries the standard and hf.* semantic-convention attributes as pure data. It emits no signal itself:
shipping is boundary I/O through an injected exporter, so observe never imports the OTel SDK (section
7.4). Pure: an Event in, a signal value out, no world, no fault.
"""

from honest_observe._util import _get
from honest_observe.types import Event

# The declared mapping of event-type suffix to OTel signal kind (section 7.1, 7.3). The suffix is the
# last dot-segment of the event type, so chain.started -> started -> a span start, link.executed ->
# executed -> a child span, persist.query -> query -> a db span, classify.completed -> completed -> a
# metric counter. One row per kind, read by subscript; a suffix the table does not name falls to the
# explicit span_event terminal below, a declared kind, not a value filed under another kind.
_SIGNAL_KIND = {
    "started": "span_start",
    "completed": "metric",
    "executed": "child_span",
    "query": "db_span",
}

# The explicit terminal signal kind for an event-type suffix the table does not name: a generic span
# event. It is a named member of the signal-kind set, so an unlisted event type produces an honest
# span event rather than being filed under one of the mapped kinds.
_DEFAULT_KIND = "span_event"


def otel_signal(event):
    """Project one event to its OpenTelemetry signal as pure data: the signal kind follows the event
    type through the declared suffix mapping (section 7.1, 7.3). The signal carries the event type and
    id and the standard and hf.* attributes. Pure: an Event in, a signal value out, no world, no
    fault."""
    event_type = event["event_type"]
    suffix = event_type.rsplit(".", 1)[-1]
    kind = _get(_SIGNAL_KIND, suffix, _DEFAULT_KIND)
    return {
        "kind": kind,
        "event_type": event_type,
        "attributes": {
            "hf.event_type": event_type,
            "hf.event_id": _get(event, "event_id", ""),
        },
    }
