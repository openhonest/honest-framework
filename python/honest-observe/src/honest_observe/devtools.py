"""Development tools (section 9): pure projections that present the log in developer-readable forms.

These tools add no instrumentation; they read what the framework already emits and choose how to show
it. They are projections, so they are pure: the format is here, and the CLI that streams the log and
prints — `honest-observe tail` — is the boundary. The print statement a developer would otherwise write
has nothing to say that the event log does not already know.

`format_tail_line` renders one event as the structured time/source/type/fields line of section 9.2. The
per-event-type field rendering is a dispatch table — the type system, not an if/elif chain — and an
event type with no entry still renders its time, source, and type with an empty field tail.
"""

_NS_PER_MS = 1_000_000


def _ms(duration_ns) -> str:
    """A nanosecond duration as a millisecond display string, one decimal place."""
    return f"{duration_ns / _NS_PER_MS:.1f}ms"


# Section 9.2 field renderers, one per event type. The table is the dispatch; an unmapped type renders
# no fields. Each renderer is a pure function of the event payload.
_TAIL_FIELDS = {
    "hf.link.executed": lambda p: f"link={p['link_name']} chain={p['chain_name']} result={p['result']} duration={_ms(p['duration_ns'])}",
    "hf.chain.started": lambda p: f"chain={p['chain_name']} links={p['link_count']}",
    "hf.chain.completed": lambda p: f"chain={p['chain_name']} result={p['result']} duration={_ms(p['duration_ns'])}",
    "hf.classify.completed": lambda p: f"tokens={p['token_count']} rejected={p['rejection_count']}",
    "hf.state.transitioned": lambda p: f"machine={p['machine_name']} {p['from_state']}->{p['to_state']}",
    "hf.request.canonical": lambda p: f"method={p['http_method']} path={p['http_path']} status={p['http_status']} duration={_ms(p['duration_ns'])}",
    "hf.browser.request": lambda p: f"method={p['method']} url={p['url']}",
    "hf.browser.response": lambda p: f"status={p['status']} duration={p['duration_ms']}ms req={p['request_id']}",
    "hf.dom.changed": lambda p: f"keys={p['changed_keys']}",
    "hf.browser.classify": lambda p: f"element={p['element']} attribute={p['attribute']}",
}


def _short_time(timestamp: str) -> str:
    """The clock portion of an ISO timestamp to millisecond precision (HH:MM:SS.mmm)."""
    return timestamp.split("T")[1].rstrip("Z")[:12]


def _tail_fields(event: dict) -> str:
    """The structured field tail for an event (section 9.2), or empty for an unmapped event type."""
    renderer = _TAIL_FIELDS.get(event["event_type"])
    return renderer(event["payload"]) if renderer else ""


def format_tail_line(event: dict) -> str:
    """One event as a tail line (section 9.2): clock time, source (server when absent), event type, and
    the event-type-specific field tail. Pure."""
    source = event.get("source", "server")
    return f"{_short_time(event['timestamp'])} {source:<7} {event['event_type']}  {_tail_fields(event)}"
