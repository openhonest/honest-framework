// Conformance for browser observability (honest-DOM spec §5). The builders are pure and mirror
// honest-observe's browser.py; emitBrowserEvent is the one boundary, taking the impure values and
// sendBeacon through injected deps. request_id is read fresh through deps.requestId, never a module var.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  browserEvent,
  browserClassify,
  browserRequest,
  browserResponse,
  domChanged,
  redact,
  readRequestId,
  emitBrowserEvent,
} from "../src/index.js";

test("browserEvent assembles the envelope with source browser and attaches request_id when supplied", () => {
  const withId = browserEvent("hf.dom.changed", "2026-01-01T00:00:00.000Z", "s1", { changed_keys: ["q"] }, "e1", "r1");
  assert.deepEqual(withId, {
    event_id: "e1",
    event_type: "hf.dom.changed",
    event_version: "1.0",
    timestamp: "2026-01-01T00:00:00.000Z",
    source: "browser",
    session_id: "s1",
    payload: { changed_keys: ["q"] },
    request_id: "r1",
  });
});

test("browserEvent omits request_id when it is null (before the first response)", () => {
  const noId = browserEvent("hf.browser.classify", "t", "s1", {}, "e1", null);
  assert.equal("request_id" in noId, false);
  assert.equal(noId.event_version, "1.0");
});

test("browserClassify carries the classification and attaches request_id only within a request", () => {
  assert.deepEqual(browserClassify("div#x", "hx-get", ["a", "b"], "search", 42, null), {
    event_type: "hf.browser.classify",
    payload: { element: "div#x", attribute: "hx-get", tokens: ["a", "b"], manifest: "search", duration_ns: 42 },
  });
  assert.deepEqual(browserClassify("div#x", "hx-get", ["a"], "search", 42, "r9"), {
    event_type: "hf.browser.classify",
    payload: { element: "div#x", attribute: "hx-get", tokens: ["a"], manifest: "search", duration_ns: 42, request_id: "r9" },
  });
});

test("browserRequest carries the request_id it sent so server events join to it", () => {
  assert.deepEqual(browserRequest("POST", "/api/search", "#btn", "#results", ["q", "page"], "r5"), {
    event_type: "hf.browser.request",
    payload: { method: "POST", url: "/api/search", trigger: "#btn", target: "#results", manifest_keys: ["q", "page"], request_id: "r5" },
  });
});

test("browserResponse joins the response to its request by request_id", () => {
  assert.deepEqual(browserResponse("r5", 200, "#results", 12.5), {
    event_type: "hf.browser.response",
    payload: { request_id: "r5", status: 200, swap_target: "#results", duration_ms: 12.5 },
  });
});

test("domChanged carries the changed keys and their new values, never the previous", () => {
  assert.deepEqual(domChanged(["q"], { q: "b" }, "r5"), {
    event_type: "hf.dom.changed",
    payload: { changed_keys: ["q"], to: { q: "b" }, request_id: "r5" },
  });
  assert.deepEqual(domChanged(["q"], { q: "b" }, null), {
    event_type: "hf.dom.changed",
    payload: { changed_keys: ["q"], to: { q: "b" } },
  });
});

test("redact keeps values in development mode and drops the new values otherwise (§5.4)", () => {
  const payload = { changed_keys: ["q"], to: { q: "b" } };
  assert.deepEqual(redact(payload, "development"), payload);
  assert.deepEqual(redact(payload, "production"), { changed_keys: ["q"] });
});

test("readRequestId returns the header value, or null when absent or empty", () => {
  assert.equal(readRequestId((name) => (name === "X-Request-ID" ? "r7" : null)), "r7");
  assert.equal(readRequestId(() => null), null);
  assert.equal(readRequestId(() => ""), null);
});

test("emitBrowserEvent builds a redacted envelope and beacons it to the ingest endpoint", () => {
  const beacons = [];
  const deps = {
    timestamp: () => "T",
    sessionId: () => "s1",
    uuid: () => "e1",
    requestId: () => "r1",
    mode: () => "production",
    sendBeacon: (endpoint, body) => beacons.push({ endpoint, body }),
  };
  emitBrowserEvent(domChanged(["q"], { q: "b" }, "r1"), deps);
  assert.equal(beacons.length, 1);
  assert.equal(beacons[0].endpoint, "/api/observe/ingest");
  const sent = JSON.parse(beacons[0].body);
  assert.equal(sent.source, "browser");
  assert.equal(sent.request_id, "r1");
  assert.deepEqual(sent.payload, { changed_keys: ["q"], request_id: "r1" });
  assert.equal("to" in sent.payload, false);
});

test("emitBrowserEvent honours a custom endpoint and keeps values in development mode", () => {
  const beacons = [];
  const deps = {
    timestamp: () => "T",
    sessionId: () => "s1",
    uuid: () => "e1",
    requestId: () => null,
    mode: () => "development",
    endpoint: "/custom/ingest",
    sendBeacon: (endpoint, body) => beacons.push({ endpoint, body }),
  };
  emitBrowserEvent(domChanged(["q"], { q: "b" }, null), deps);
  assert.equal(beacons[0].endpoint, "/custom/ingest");
  const sent = JSON.parse(beacons[0].body);
  assert.equal("request_id" in sent, false);
  assert.deepEqual(sent.payload.to, { q: "b" });
});
