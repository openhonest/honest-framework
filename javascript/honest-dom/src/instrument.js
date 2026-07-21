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
import { emitBrowserEvent, browserRequest, browserResponse, domChanged, readRequestId } from "./browser.js";
import { collect } from "./collect.js";
import { apply } from "./apply.js";

export const REQUEST_ID_ATTR = "data-request-id";
// Where the reload-recovery snapshot of manifest state lives (§5.5), and how long it stays valid — the
// same time bound send/replay use (§2.6).
const STATE_KEY = "domx:state";
const STATE_TTL_MS = 300000;

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

// A stable descriptor for an element in a browser event: its `#id` when it has one, else its tag name.
// An absent element is the empty string. Pure.
export function describeElement(el) {
  if (el === null || el === undefined) {
    return "";
  }
  return el.id ? `#${el.id}` : el.tagName.toLowerCase();
}

// The manifest keys a request carries, for the browser.request payload: the keys of the collected state
// domx put in the `_state` parameter, or the raw parameter names when no state was collected. Pure.
export function manifestKeysOf(parameters) {
  return parameters._state === undefined ? Object.keys(parameters) : Object.keys(JSON.parse(parameters._state));
}

// Adapt a real HTMX lifecycle event's detail to onHtmxEvent's normalized shape. dict-dispatch keyed by
// event name; each reads only documented htmx detail fields (requestConfig.verb/path, elt, target, xhr,
// requestConfig.parameters) and measures the request's duration off its own xhr — request-scoped, so
// concurrent requests never clobber one another's start time.
const _ADAPT = {
  "htmx:beforeRequest": (evt, deps) => {
    evt.detail.xhr._domxStart = deps.now();
    onHtmxEvent("htmx:beforeRequest", {
      method: evt.detail.requestConfig.verb,
      url: evt.detail.requestConfig.path,
      trigger: describeElement(evt.detail.elt),
      target: describeElement(evt.detail.target),
      manifestKeys: manifestKeysOf(evt.detail.requestConfig.parameters),
    }, deps);
  },
  "htmx:afterRequest": (evt, deps) => {
    onHtmxEvent("htmx:afterRequest", {
      getHeader: (name) => evt.detail.xhr.getResponseHeader(name),
      status: evt.detail.xhr.status,
      target: describeElement(evt.detail.target),
      durationMs: deps.now() - (evt.detail.xhr._domxStart ?? deps.now()),
    }, deps);
  },
};

// Register the domx observability extension through the injected htmx (never a global): every HTMX
// request and response is beaconed automatically (§5.3), with no developer code. This is the real-browser
// binding — its end-to-end behaviour against live htmx is verified by the browser conformance suite
// (§8.2, a real headless browser), not this mock-level gate; here a fake htmx and fake events cover it.
export function registerInstrumentation(htmx, deps) {
  htmx.defineExtension("domx-observe", {
    onEvent(name, evt) {
      const adapt = _ADAPT[name];
      if (adapt !== undefined) {
        adapt(evt, deps);
      }
    },
  });
}

// The manifest keys whose value changed against a previous snapshot, with their new values. Pure: a deep
// compare through canonical JSON, so a key absent from the previous snapshot reads as changed.
export function stateDiff(previous, current) {
  const changedKeys = [];
  const to = {};
  for (const key of Object.keys(current)) {
    if (JSON.stringify(current[key]) !== JSON.stringify(previous[key])) {
      changedKeys.push(key);
      to[key] = current[key];
    }
  }
  return { changed_keys: changedKeys, to };
}

// Instrument manifest state changes (§5.3, §5.5): on every change the injected observer detects, beacon
// hf.dom.changed with the changed slots and their new values, and cache the current state to localStorage
// so a reload can restore it. The previous snapshot for the diff is that same cache — written from the
// DOM on every change and read only here and on restore, never a live second source. Returns the
// observer's unsubscribe.
export function instrumentChanges(manifest, deps) {
  return deps.bus.onMutation(() =>
    deps.bus.schedule(() => {
      const current = collect(manifest, deps.query);
      const cached = deps.getItem(STATE_KEY);
      const { changed_keys, to } = stateDiff(cached === null ? {} : cached.state, current);
      if (changed_keys.length > 0) {
        emitBrowserEvent(domChanged(changed_keys, to, deps.requestId()), deps);
        deps.setItem(STATE_KEY, { state: current, timestamp: deps.now() });
      }
    }),
  );
}

// Restore manifest state from the reload-recovery cache (§5.5): a reload discards the DOM state, so apply
// the cached state over the freshly rendered page — unless the cache is absent or past its time bound.
export function restoreState(manifest, deps) {
  const cached = deps.getItem(STATE_KEY);
  if (cached !== null && deps.now() - cached.timestamp <= STATE_TTL_MS) {
    apply(manifest, cached.state, deps.query);
  }
}
