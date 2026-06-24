"""Development tools (section 9): pure projections that present the log in developer-readable forms.

These tools add no instrumentation; they read what the framework already emits and choose how to show
it. They are projections, so they are pure: the format is here, and the CLI that streams the log and
prints — `honest-observe tail` — is the boundary. The print statement a developer would otherwise write
has nothing to say that the event log does not already know.

`format_tail_line` renders one event as the structured time/source/type/fields line of section 9.2. The
per-event-type field rendering is a dispatch table — the type system, not an if/elif chain — and an
event type with no entry still renders its time, source, and type with an empty field tail.

`run_named_projection` (section 9.4) resolves a projection by name from a registry and runs it over the
events; this is what `honest-observe query` calls once the CLI has read the log.
"""

from honest_type import err, fault, ok

from honest_observe.projections import apply_projection

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


def _whole_ms(ms_value) -> str:
    """A millisecond quantity as a whole-millisecond display string (the inspect tier totals)."""
    return f"{round(ms_value)}ms"


# Section 9.3 browser-line detail, one renderer per automatic browser event type (section 8.4). The
# four types are the closed set a browser trace can contain, so the lookup is direct.
_INSPECT_DETAIL = {
    "hf.dom.changed": lambda p: f"{p['changed_keys']}",
    "hf.browser.request": lambda p: f"{p['method']} {p['url']}",
    "hf.browser.response": lambda p: f"{p['status']}  {p['swap_target']}  {p['duration_ms']}ms",
    "hf.browser.classify": lambda p: f"{p['element']}  {p['attribute']}",
}


def _request_id_of(event: dict):
    """The request_id an event carries, wherever it is present (section 9.3): the envelope field on a
    browser event, the payload on a server event that includes one, or the aggregate_id of a
    request-aggregate event. None when the event carries no request_id."""
    if "request_id" in event:
        return event["request_id"]
    if "request_id" in event["payload"]:
        return event["payload"]["request_id"]
    if event.get("aggregate_type") == "request":
        return event["aggregate_id"]
    return None


def _browser_line(event: dict) -> str:
    """One browser event as an inspect line (section 9.3): clock time, the abbreviated event type, and
    its detail."""
    detail = _INSPECT_DETAIL[event["event_type"]](event["payload"])
    return f"  {_short_time(event['timestamp'])}  {event['event_type'].removeprefix('hf.')}  {detail}"


def _server_lines(canonical_payload: dict) -> list:
    """The server section of an inspect trace (section 9.3): one line per link in the canonical event's
    denormalized link_sequence — name, result, duration, and the fault code on an errored link. No
    per-link timestamp, because the canonical record holds durations, not per-link wall-clock."""
    return [
        f"  link  {s['link_name']}  {s['result']}  {_ms(s['duration_ns'])}" + (f"  {s['fault_code']}" if "fault_code" in s else "")
        for s in canonical_payload["link_sequence"]
    ]


def _inspect_breakdown(canonical_payload: dict, browser_events: list):
    """The single-clock timing breakdown for a request (section 9.3): server from the canonical
    duration, network from the browser round trip minus server, browser from the sum of browser-local
    durations, total as their sum. Returns (server_ms, network_ms, browser_ms, total_ms)."""
    server_ms = canonical_payload["duration_ns"] / _NS_PER_MS
    response = next((e for e in browser_events if e["event_type"] == "hf.browser.response"), None)
    network_ms = response["payload"]["duration_ms"] - server_ms if response else 0
    browser_ms = sum(e["payload"]["duration_ns"] / _NS_PER_MS for e in browser_events if e["event_type"] == "hf.browser.classify")
    return server_ms, network_ms, browser_ms, server_ms + network_ms + browser_ms


def format_inspect(request_id: str, events: list) -> str:
    """A request's execution trace (section 9.3). Pure. Correlates by request_id: the server trace is
    the canonical event's link_sequence, the browser trace is the browser events carrying the
    request_id, ordered BROWSER -> SERVER -> BROWSER by timestamp. The footer attributes the elapsed
    time across the tiers from single-clock durations."""
    canonical = next(e for e in events if e.get("aggregate_type") == "request" and e.get("aggregate_id") == request_id)
    payload = canonical["payload"]
    browser = [e for e in events if e.get("source") == "browser" and _request_id_of(e) == request_id]
    before = sorted((e for e in browser if e["timestamp"] < canonical["timestamp"]), key=lambda e: e["timestamp"])
    after = sorted((e for e in browser if e["timestamp"] >= canonical["timestamp"]), key=lambda e: e["timestamp"])
    server_ms, network_ms, browser_ms, total_ms = _inspect_breakdown(payload, browser)

    sections = []
    if before:
        sections.append("BROWSER\n" + "\n".join(_browser_line(e) for e in before))
    sections.append("SERVER\n" + "\n".join(_server_lines(payload)))
    if after:
        sections.append("BROWSER\n" + "\n".join(_browser_line(e) for e in after))

    header = f"Request: {request_id}\n{payload['http_method']} {payload['http_path']} → {payload['http_status']}  total: {_whole_ms(total_ms)}"
    footer = f"Total: {_whole_ms(total_ms)}  (server: {_whole_ms(server_ms)}  network: {_whole_ms(network_ms)}  browser: {_whole_ms(browser_ms)})"
    return header + "\n\n" + "\n\n".join(sections) + "\n\n" + footer


def run_named_projection(registry: dict, name: str, events: list):
    """Run a projection resolved by name from a registry (section 9.4). Pure: look up the declared
    projection (a declare_projection result), then fold the events through it with its filters and
    initial state. Returns ok(state), or err(fault 'unknown_projection') when the name is not
    registered — the events are passed in, so reading the log stays the CLI's concern."""
    declaration = registry.get(name)
    if declaration is None:
        return err(fault("unknown_projection", f"No projection named '{name}' in the registry", "client", {"name": name}))
    state = apply_projection(
        events,
        declaration["fold"],
        declaration["initial_state"],
        event_types=declaration.get("event_types"),
        aggregate_type=declaration.get("aggregate_type"),
        aggregate_id=declaration.get("aggregate_id"),
    )
    return ok(state)
