// Conformance for the HTMX instrumentation wiring (honest-DOM §5.2-5.3): request_id lives in the DOM
// and is read fresh; each HTMX lifecycle event emits its browser event. The DOM and the browser runtime
// are injected, so the dispatch is tested with plain fakes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { currentRequestId, storeRequestId, onHtmxEvent, describeElement, manifestKeysOf, registerInstrumentation, stateDiff, instrumentChanges, restoreState } from "../src/index.js";

const fakeRoot = () => {
  const attrs = {};
  return {
    attrs,
    getAttribute: (name) => (name in attrs ? attrs[name] : null),
    setAttribute: (name, value) => (attrs[name] = value),
  };
};

const emitDeps = (root, over = {}) => {
  const beacons = [];
  return {
    root,
    beacons,
    timestamp: () => "T",
    sessionId: () => "s1",
    uuid: () => "e1",
    mode: () => over.mode ?? "production",
    requestId: () => currentRequestId(root),
    sendBeacon: (endpoint, body) => beacons.push({ endpoint, body }),
  };
};

test("currentRequestId reads the request_id from the DOM, or null when absent", () => {
  const root = fakeRoot();
  assert.equal(currentRequestId(root), null);
  root.setAttribute("data-request-id", "r1");
  assert.equal(currentRequestId(root), "r1");
});

test("storeRequestId writes a request_id to the DOM but leaves the previous value on a null id", () => {
  const root = fakeRoot();
  storeRequestId(root, "r1");
  assert.equal(root.attrs["data-request-id"], "r1");
  storeRequestId(root, null);
  assert.equal(root.attrs["data-request-id"], "r1");
});

test("onHtmxEvent on beforeRequest emits browser.request carrying the current request_id", () => {
  const root = fakeRoot();
  root.setAttribute("data-request-id", "r0");
  const deps = emitDeps(root);
  onHtmxEvent(
    "htmx:beforeRequest",
    { method: "POST", url: "/api/search", trigger: "#btn", target: "#results", manifestKeys: ["q"] },
    deps,
  );
  assert.equal(deps.beacons.length, 1);
  const sent = JSON.parse(deps.beacons[0].body);
  assert.equal(sent.event_type, "hf.browser.request");
  assert.equal(sent.request_id, "r0");
  assert.equal(sent.payload.request_id, "r0");
  assert.equal(sent.payload.url, "/api/search");
});

test("onHtmxEvent on afterRequest stores the response's request_id then emits browser.response with it", () => {
  const root = fakeRoot();
  const deps = emitDeps(root);
  onHtmxEvent(
    "htmx:afterRequest",
    { getHeader: (name) => (name === "X-Request-ID" ? "r9" : null), status: 200, target: "#results", durationMs: 12.5 },
    deps,
  );
  assert.equal(root.attrs["data-request-id"], "r9");
  const sent = JSON.parse(deps.beacons[0].body);
  assert.equal(sent.event_type, "hf.browser.response");
  assert.equal(sent.request_id, "r9");
  assert.deepEqual(sent.payload, { request_id: "r9", status: 200, swap_target: "#results", duration_ms: 12.5 });
});

test("onHtmxEvent ignores a lifecycle event with no browser-event mapping", () => {
  const root = fakeRoot();
  const deps = emitDeps(root);
  assert.equal(onHtmxEvent("htmx:oobBeforeSwap", {}, deps), undefined);
  assert.equal(deps.beacons.length, 0);
});

test("describeElement gives an element's #id, else its tag name, and empty for none", () => {
  assert.equal(describeElement({ id: "results", tagName: "DIV" }), "#results");
  assert.equal(describeElement({ id: "", tagName: "BUTTON" }), "button");
  assert.equal(describeElement(null), "");
  assert.equal(describeElement(undefined), "");
});

test("manifestKeysOf reads the collected state's keys, or the raw parameter names", () => {
  assert.deepEqual(manifestKeysOf({ _state: JSON.stringify({ q: "hi", page: 2 }) }), ["q", "page"]);
  assert.deepEqual(manifestKeysOf({ q: "hi", page: "2" }), ["q", "page"]);
});

// A fake htmx that captures the extension the module registers, plus a fake lifecycle event.
const fakeHtmx = () => {
  const registered = {};
  return { registered, defineExtension: (name, ext) => { registered.name = name; registered.ext = ext; }, deliver: (name, evt) => registered.ext.onEvent(name, evt) };
};

test("registerInstrumentation beacons a browser.request on beforeRequest, carrying the current request_id", () => {
  const root = fakeRoot();
  root.setAttribute("data-request-id", "r0");
  const deps = { ...emitDeps(root), now: () => 1000 };
  const htmx = fakeHtmx();
  registerInstrumentation(htmx, deps);
  assert.equal(htmx.registered.name, "domx-observe"); // registered under the domx observability extension name
  const xhr = { getResponseHeader: () => null, status: 200 };
  htmx.deliver("htmx:beforeRequest", { detail: { xhr, requestConfig: { verb: "post", path: "/api/search", parameters: { _state: JSON.stringify({ q: "hi" }) } }, elt: { id: "btn", tagName: "BUTTON" }, target: { id: "results", tagName: "DIV" } } });
  assert.equal(xhr._domxStart, 1000); // start stamped on the request's own xhr
  const sent = JSON.parse(deps.beacons[0].body);
  assert.equal(sent.event_type, "hf.browser.request");
  assert.deepEqual(sent.payload, { method: "post", url: "/api/search", trigger: "#btn", target: "#results", manifest_keys: ["q"], request_id: "r0" });
});

test("registerInstrumentation beacons a browser.response on afterRequest, with the measured duration", () => {
  const root = fakeRoot();
  let clock = 1000;
  const deps = { ...emitDeps(root), now: () => clock };
  const htmx = fakeHtmx();
  registerInstrumentation(htmx, deps);
  const xhr = { getResponseHeader: (name) => (name === "X-Request-ID" ? "r9" : null), status: 200 };
  htmx.deliver("htmx:beforeRequest", { detail: { xhr, requestConfig: { verb: "get", path: "/x", parameters: {} }, elt: null, target: { id: "results", tagName: "DIV" } } });
  clock = 1012;
  htmx.deliver("htmx:afterRequest", { detail: { xhr, target: { id: "results", tagName: "DIV" } } });
  assert.equal(root.attrs["data-request-id"], "r9"); // response's request_id stored in the DOM
  const response = JSON.parse(deps.beacons[1].body);
  assert.equal(response.event_type, "hf.browser.response");
  assert.deepEqual(response.payload, { request_id: "r9", status: 200, swap_target: "#results", duration_ms: 12 });
});

test("registerInstrumentation reports a zero duration when no start was stamped", () => {
  const root = fakeRoot();
  const deps = { ...emitDeps(root), now: () => 5000 };
  const htmx = fakeHtmx();
  registerInstrumentation(htmx, deps);
  const xhr = { getResponseHeader: () => null, status: 204 }; // afterRequest with no preceding beforeRequest
  htmx.deliver("htmx:afterRequest", { detail: { xhr, target: null } });
  assert.equal(JSON.parse(deps.beacons[0].body).payload.duration_ms, 0);
});

test("registerInstrumentation ignores an htmx event it does not instrument", () => {
  const root = fakeRoot();
  const deps = emitDeps(root);
  const htmx = fakeHtmx();
  registerInstrumentation(htmx, deps);
  htmx.deliver("htmx:load", { detail: {} });
  assert.equal(deps.beacons.length, 0);
});

test("stateDiff reports the keys whose value changed, with their new values", () => {
  assert.deepEqual(stateDiff({ q: "a", page: 1 }, { q: "b", page: 1 }), { changed_keys: ["q"], to: { q: "b" } });
  assert.deepEqual(stateDiff({}, { tags: ["x"] }), { changed_keys: ["tags"], to: { tags: ["x"] } }); // absent-before reads as changed
  assert.deepEqual(stateDiff({ q: "a" }, { q: "a" }), { changed_keys: [], to: {} }); // nothing changed
});

// A fake change bus and a fake store, plus emit deps and a query for collect.
const changeDeps = (over = {}) => {
  const store = {};
  let onChange = null;
  const beacons = [];
  return {
    beacons,
    store,
    fireChange: () => onChange(),
    bus: { onMutation: (cb) => { onChange = cb; return () => { onChange = null; }; }, schedule: (fn) => fn() },
    query: (sel) => over.matches?.[sel] ?? [],
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, obj) => (store[key] = obj),
    now: () => over.now ?? 1000,
    timestamp: () => "T",
    sessionId: () => "s1",
    uuid: () => "e1",
    mode: () => "development",
    requestId: () => null,
    sendBeacon: (endpoint, body) => beacons.push({ endpoint, body }),
  };
};

test("instrumentChanges beacons dom.changed and caches the new state on a change", () => {
  const deps = changeDeps({ matches: { "#q": [{ value: "hi" }] }, now: 5000 });
  const manifest = { q: { selector: "#q", read: "value" } };
  instrumentChanges(manifest, deps);
  deps.fireChange();
  const sent = JSON.parse(deps.beacons[0].body);
  assert.equal(sent.event_type, "hf.dom.changed");
  assert.deepEqual(sent.payload, { changed_keys: ["q"], to: { q: "hi" } });
  assert.deepEqual(deps.store["domx:state"], { state: { q: "hi" }, timestamp: 5000 }); // cached for reload recovery
});

test("instrumentChanges emits nothing and caches nothing when the state is unchanged", () => {
  const deps = changeDeps({ matches: { "#q": [{ value: "hi" }] } });
  deps.store["domx:state"] = { state: { q: "hi" }, timestamp: 1 };
  instrumentChanges({ q: { selector: "#q", read: "value" } }, deps);
  deps.fireChange();
  assert.equal(deps.beacons.length, 0);
  assert.equal(deps.store["domx:state"].timestamp, 1); // unchanged, cache untouched
});

test("restoreState applies the cached state after a reload, unless absent or expired", () => {
  const manifest = { q: { selector: "#q", write: "attr:value" } };
  // Each case gets its own written target and its own store, so getItem reads the case's own cache.
  const mk = (now) => {
    const written = {};
    const deps = changeDeps({ matches: { "#q": [{ setAttribute: (n, v) => (written[n] = v) }] }, now });
    return { written, deps };
  };

  const none = mk(1000);
  restoreState(manifest, none.deps); // no cache -> nothing applied
  assert.deepEqual(none.written, {});

  const fresh = mk(1000);
  fresh.deps.store["domx:state"] = { state: { q: "hi" }, timestamp: 900 };
  restoreState(manifest, fresh.deps); // within the 5-minute bound -> applied
  assert.equal(fresh.written.value, "hi");

  const expired = mk(500000);
  expired.deps.store["domx:state"] = { state: { q: "old" }, timestamp: 100 }; // 500000 - 100 > the bound
  restoreState(manifest, expired.deps); // past the bound -> not applied
  assert.deepEqual(expired.written, {});

  const atBound = mk(300100);
  atBound.deps.store["domx:state"] = { state: { q: "edge" }, timestamp: 100 }; // exactly at the 300000 bound -> applied
  restoreState(manifest, atBound.deps);
  assert.equal(atBound.written.value, "edge");

  const pastBound = mk(300101);
  pastBound.deps.store["domx:state"] = { state: { q: "old" }, timestamp: 100 }; // one tick past the bound -> not applied
  restoreState(manifest, pastBound.deps);
  assert.deepEqual(pastBound.written, {});
});
