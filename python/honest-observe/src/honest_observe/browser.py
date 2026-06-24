"""Browser instrumentation (section 8): the browser event envelope and the automatic browser events.

Browser-side events are beaconed to the same log as server events and joined to them by `request_id` —
one log, both sides. The pieces here are the pure data contracts: the envelope a browser event takes
(section 8.2) and the four events the DOM bootloader and domx emit automatically (section 8.4). The
beacon itself (`navigator.sendBeacon`) and the ingest endpoint that validates the session, stamps
`received_at`, and appends are boundary I/O — the browser event shape is what that endpoint validates
against and what tests assemble, exactly as `build_event` is the server envelope without the write.

The browser envelope differs from the server one: it carries `source: "browser"` and a `session_id`,
joins to server events through an optional `request_id`, and has no aggregate or sequence fields. The
impure values — a v4 `event_id` generated in the browser, a `timestamp` from the performance clock —
are passed in, so assembly stays pure.
"""

from honest_type import err, fault, ok

# A browser event cannot be valid without these (non-empty strings). `source` is the constant
# "browser"; `payload` may be empty; `request_id` is optional (absent before the first response).
_BROWSER_REQUIRED = ("event_id", "event_type", "event_version", "timestamp", "session_id")


def build_browser_event(event_type, event_version, timestamp, session_id, payload, event_id, request_id=None):
    """Assemble a validated browser event envelope (section 8.2). Pure. `source` is always "browser";
    `request_id` is attached only when supplied (it joins to the server events the browser event
    triggered). Returns ok(event), or err(fault 'invalid_event') naming any required field left empty."""
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": event_version,
        "timestamp": timestamp,
        "source": "browser",
        "session_id": session_id,
        "payload": payload,
    }
    if request_id is not None:
        event["request_id"] = request_id
    missing = [name for name in _BROWSER_REQUIRED if not event[name]]
    if missing:
        return err(fault("invalid_event", f"Browser event is missing required field(s): {missing}", "client", {"missing": missing}))
    return ok(event)


def browser_classify(element, attribute, tokens, manifest, duration_ns, request_id=None):
    """The hf.browser.classify event payload (section 8.4): one attribute classification by the
    bootloader. `request_id` appears only within a request context. Pure."""
    payload = {"element": element, "attribute": attribute, "tokens": list(tokens), "manifest": manifest, "duration_ns": duration_ns}
    if request_id is not None:
        payload["request_id"] = request_id
    return {"event_type": "hf.browser.classify", "payload": payload}


def browser_request(method, url, trigger, target, manifest_keys, request_id):
    """The hf.browser.request event payload (section 8.4): one HTMX request from domx, carrying the
    request_id it sent so server events join to it. Pure."""
    return {"event_type": "hf.browser.request", "payload": {"method": method, "url": url, "trigger": trigger, "target": target, "manifest_keys": list(manifest_keys), "request_id": request_id}}


def browser_response(request_id, status, swap_target, duration_ms):
    """The hf.browser.response event payload (section 8.4): one HTMX response arriving, joined to its
    request and the server events by request_id. Pure."""
    return {"event_type": "hf.browser.response", "payload": {"request_id": request_id, "status": status, "swap_target": swap_target, "duration_ms": duration_ms}}


def dom_changed(changed_keys, from_values, to_values, request_id=None):
    """The hf.dom.changed event payload (section 8.4): a manifest state change seen by domx's mutation
    observer, with the previous and new values for the changed slots. `request_id` appears only when the
    change happens within a request context. Pure."""
    payload = {"changed_keys": list(changed_keys), "from": from_values, "to": to_values}
    if request_id is not None:
        payload["request_id"] = request_id
    return {"event_type": "hf.dom.changed", "payload": payload}
