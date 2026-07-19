// Automatic browser-event emission (honest-DOM §5.2-5.3): domx instruments HTMX so every request and
// response is beaconed with no developer code. The request_id from each response lives in the DOM —
// documentElement's data-request-id — and is read fresh for every event, never a module variable, so
// there is no second hidden mutator of shared state (the single-mutator law: the DOM is the store). The
// browser runtime (sendBeacon, crypto, the performance clock, the session cookie, the mode meta tag,
// and the DOM read/write of request_id) is injected as deps; the dispatch here is pure.
//
// onHtmxEvent takes a normalized lifecycle detail; adapting a real htmx event's detail to that shape,
// and wiring the observer's old-values for dom.changed and the bootloader's classify events, is the
// real-browser binding verified by the browser conformance suite (§8.2), not this mock-level gate.
import { emitBrowserEvent, browserRequest, browserResponse, readRequestId } from "./browser.js";

export const REQUEST_ID_ATTR = "data-request-id";

// Read the current request_id from the DOM (§5.2). Pure given the root element; an absent attribute
// (before the first response) is null.
export function currentRequestId(root) {
  return root.getAttribute(REQUEST_ID_ATTR) || null;
}

// Store a response's request_id into the DOM so later events read it fresh (§5.2). A null id — a
// response without the header — leaves the previous value in place. Boundary: writes the DOM.
export function storeRequestId(root, requestId) {
  return requestId === null ? undefined : root.setAttribute(REQUEST_ID_ATTR, requestId);
}

// Map each HTMX lifecycle event to the browser event it emits (§5.3). dict-dispatch, not if/elif.
const ON_HTMX = {
  "htmx:beforeRequest": (detail, deps) =>
    emitBrowserEvent(
      browserRequest(detail.method, detail.url, detail.trigger, detail.target, detail.manifestKeys, deps.requestId()),
      deps,
    ),
  "htmx:afterRequest": (detail, deps) => {
    storeRequestId(deps.root, readRequestId(detail.getHeader));
    emitBrowserEvent(browserResponse(deps.requestId(), detail.status, detail.target, detail.durationMs), deps);
  },
};

// Emit the browser event for one normalized HTMX lifecycle event; an event with no mapping is ignored.
export function onHtmxEvent(name, detail, deps) {
  const handler = ON_HTMX[name];
  return handler === undefined ? undefined : handler(detail, deps);
}
