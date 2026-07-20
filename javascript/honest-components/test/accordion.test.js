// Conformance for the accordion behaviour (honest-components §2.4). The accordion owns only its
// specifics — accordionExpanded reads its aria-expanded state, accordionHandle computes the change an
// event produces — and composes the shared enhancement runtime (exercised in enhance.test.js). Pure over
// plain element mocks; no real DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ACCORDION_EVENTS, accordionExpanded, accordionHandle } from "../src/index.js";

// A DOM-like element mock: attributes over a store.
const el = (attrs = {}) => {
  const store = { ...attrs };
  return {
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, v) => { store[name] = String(v); },
    _store: store,
  };
};

test("ACCORDION_EVENTS are the click and keydown an accordion header listens on", () => {
  assert.deepEqual(ACCORDION_EVENTS, ["click", "keydown"]);
});

test("accordionExpanded negates the DOM's current expanded state", () => {
  assert.equal(accordionExpanded(el({ "aria-expanded": "true" })), false);
  assert.equal(accordionExpanded(el({ "aria-expanded": "false" })), true);
  assert.equal(accordionExpanded(el({})), true); // absent reads as collapsed
});

test("accordionHandle toggles on a click and on an activation key, and no-ops on another key", () => {
  assert.deepEqual(accordionHandle(el({ "aria-expanded": "false" }), { type: "click" }), { "aria-expanded": "true", _preventDefault: false });
  assert.deepEqual(accordionHandle(el({ "aria-expanded": "true" }), { type: "click" }), { "aria-expanded": "false", _preventDefault: false });
  assert.deepEqual(accordionHandle(el({ "aria-expanded": "false" }), { type: "keydown", key: "Enter" }), { "aria-expanded": "true", _preventDefault: true });
  assert.deepEqual(accordionHandle(el({ "aria-expanded": "false" }), { type: "keydown", key: " " }), { "aria-expanded": "true", _preventDefault: true });
  assert.equal(accordionHandle(el({ "aria-expanded": "false" }), { type: "keydown", key: "a" }), null); // non-activation key
});
