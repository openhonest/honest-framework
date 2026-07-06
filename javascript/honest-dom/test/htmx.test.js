// Conformance for the HTMX extension (honest-DOM spec §3): collect state automatically before every
// HTMX request. nearestManifest walks the ancestor chain for a dx-manifest attribute (pure, over
// plain-object elements). configureRequest resolves that manifest, collects, and merges the state into
// the request parameters as _state. registerExtension defines the extension through an injected htmx,
// so the only real-browser glue is the caller passing window.htmx and a resolver over the global scope.
import { test } from "node:test";
import assert from "node:assert/strict";
import { nearestManifest, configureRequest, registerExtension } from "../src/index.js";

// A plain-object element: getAttribute reads its own attrs; parentElement links the chain.
const el = (attrs, parentElement = null) => ({
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
  parentElement,
});

test("nearestManifest returns the element's own dx-manifest", () => {
  assert.equal(nearestManifest(el({ "dx-manifest": "appManifest" })), "appManifest");
});

test("nearestManifest returns the nearest ancestor's dx-manifest", () => {
  const root = el({ "dx-manifest": "appManifest" });
  const mid = el({}, root);
  const button = el({}, mid);
  assert.equal(nearestManifest(button), "appManifest");
});

test("nearestManifest returns null when no ancestor declares one", () => {
  const root = el({});
  const button = el({}, root);
  assert.equal(nearestManifest(button), null);
});

test("configureRequest collects the resolved manifest and merges _state", () => {
  const manifest = { q: { selector: "#q", read: "value" } };
  const detail = { elt: el({ "dx-manifest": "appManifest" }), parameters: {} };
  const deps = { resolveManifest: (name) => (name === "appManifest" ? manifest : null), query: (sel) => [{ value: "hi" }] };
  configureRequest(detail, deps);
  assert.equal(detail.parameters._state, JSON.stringify({ q: "hi" }));
});

test("configureRequest leaves the parameters untouched when no manifest is in scope", () => {
  const detail = { elt: el({}), parameters: {} };
  const deps = { resolveManifest: () => null, query: () => [] };
  configureRequest(detail, deps);
  assert.deepEqual(detail.parameters, {});
});

test("registerExtension defines a domx extension that runs on configRequest only", () => {
  let defined;
  const htmx = { defineExtension: (name, ext) => (defined = { name, ext }) };
  const manifest = { q: { selector: "#q", read: "value" } };
  const deps = { resolveManifest: () => manifest, query: () => [{ value: "hi" }] };
  registerExtension(htmx, deps);
  assert.equal(defined.name, "domx");
  const detail = { elt: el({ "dx-manifest": "appManifest" }), parameters: {} };
  defined.ext.onEvent("htmx:configRequest", { detail });
  assert.equal(detail.parameters._state, JSON.stringify({ q: "hi" }));
  const other = { elt: el({ "dx-manifest": "appManifest" }), parameters: {} };
  defined.ext.onEvent("htmx:afterRequest", { detail: other });
  assert.deepEqual(other.parameters, {});
});
