// Browser observability (honest-DOM spec §5): domx is honest-observe's browser-side instrumentation.
// Every browser event is beaconed to /api/observe/ingest and joins the server log by request_id — one
// log, both sides. The event builders are pure and mirror honest-observe's browser.py contract field
// for field; emitBrowserEvent is the one boundary, taking the impure values (event_id, timestamp,
// session_id, request_id, mode) and sendBeacon through injected deps so assembly stays pure. request_id
// is never held in a module variable — that would be a second, hidden mutator of shared state. It lives
// in the DOM, written on each HTMX response and read fresh at emit time through deps.requestId (§5.2).

const EVENT_VERSION = "1.0";
const INGEST_ENDPOINT = "/api/observe/ingest";
// Payload fields that carry user-state values. Dropped outside development mode (§5.4): a browser event
// records which slots changed, never what they changed to.
const VALUE_BEARING = ["from", "to"];

// Assemble a browser event envelope (§5.1). Pure. source is always "browser"; request_id is attached
// only when supplied (null before the first response), since it joins to the server events triggered.
export function browserEvent(eventType, timestamp, sessionId, payload, eventId, requestId) {
  const event = {
    event_id: eventId,
    event_type: eventType,
    event_version: EVENT_VERSION,
    timestamp,
    source: "browser",
    session_id: sessionId,
    payload,
  };
  return requestId === null ? event : { ...event, request_id: requestId };
}

// The four automatic event payloads (§5.3), mirroring honest-observe's browser.py. Each is pure and
// returns { event_type, payload } — the shape emitBrowserEvent wraps in an envelope.

export function browserClassify(element, attribute, tokens, manifest, durationNs, requestId) {
  const payload = { element, attribute, tokens: [...tokens], manifest, duration_ns: durationNs };
  return requestId === null
    ? { event_type: "hf.browser.classify", payload }
    : { event_type: "hf.browser.classify", payload: { ...payload, request_id: requestId } };
}

export function browserRequest(method, url, trigger, target, manifestKeys, requestId) {
  return {
    event_type: "hf.browser.request",
    payload: { method, url, trigger, target, manifest_keys: [...manifestKeys], request_id: requestId },
  };
}

export function browserResponse(requestId, status, swapTarget, durationMs) {
  return {
    event_type: "hf.browser.response",
    payload: { request_id: requestId, status, swap_target: swapTarget, duration_ms: durationMs },
  };
}

export function domChanged(changedKeys, fromValues, toValues, requestId) {
  const payload = { changed_keys: [...changedKeys], from: fromValues, to: toValues };
  return requestId === null
    ? { event_type: "hf.dom.changed", payload }
    : { event_type: "hf.dom.changed", payload: { ...payload, request_id: requestId } };
}

// Strip value-bearing fields unless in development mode (§5.4). Pure: keys survive, values do not.
export function redact(payload, mode) {
  return mode === "development"
    ? payload
    : Object.fromEntries(Object.entries(payload).filter(([key]) => !VALUE_BEARING.includes(key)));
}

// Read X-Request-ID from a response header getter (§5.2). Pure: an absent or empty header is null.
export function readRequestId(getHeader) {
  return getHeader("X-Request-ID") || null;
}

// The one boundary: build the envelope from injected impure values and beacon it (§5.1). request_id is
// read fresh from the DOM through deps.requestId, so no module state holds it between requests.
export function emitBrowserEvent(event, deps) {
  const envelope = browserEvent(
    event.event_type,
    deps.timestamp(),
    deps.sessionId(),
    redact(event.payload, deps.mode()),
    deps.uuid(),
    deps.requestId(),
  );
  deps.sendBeacon(deps.endpoint ?? INGEST_ENDPOINT, JSON.stringify(envelope));
}
