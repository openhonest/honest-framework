// Conformance for the HTMX instrumentation wiring (honest-DOM §5.2-5.3): request_id lives in the DOM
// and is read fresh; each HTMX lifecycle event emits its browser event. The DOM and the browser runtime
// are injected, so the dispatch is tested with plain fakes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { currentRequestId, storeRequestId, onHtmxEvent } from "../src/index.js";

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
