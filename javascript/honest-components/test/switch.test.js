// Conformance for the switch behaviour (honest-components §2.4). The switch owns only its specifics —
// toggled reads its aria-checked state, handle computes the change an event produces — and composes the
// shared enhancement runtime (exercised in enhance.test.js). Pure over plain element objects; no real DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import { SWITCH_EVENTS, handle, toggled } from "../src/index.js";

// A DOM-like element: attributes over a store.
const el = (attrs = {}) => {
  const store = { ...attrs };
  return {
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, v) => { store[name] = String(v); },
    _store: store,
  };
};

test("SWITCH_EVENTS are the click and keydown a switch listens on", () => {
  assert.deepEqual(SWITCH_EVENTS, ["click", "keydown"]);
});

test("toggled negates the DOM's current checked state", () => {
  assert.equal(toggled(el({ "aria-checked": "true" })), false);
  assert.equal(toggled(el({ "aria-checked": "false" })), true);
  assert.equal(toggled(el({})), true); // absent reads as not-checked
});

test("handle toggles on a click and on a toggle key, and no-ops on another key", () => {
  assert.deepEqual(handle(el({ "aria-checked": "false" }), { type: "click" }), { "aria-checked": "true", _preventDefault: false });
  assert.deepEqual(handle(el({ "aria-checked": "true" }), { type: "click" }), { "aria-checked": "false", _preventDefault: false });
  assert.deepEqual(handle(el({ "aria-checked": "false" }), { type: "keydown", key: "Enter" }), { "aria-checked": "true", _preventDefault: true });
  assert.deepEqual(handle(el({ "aria-checked": "false" }), { type: "keydown", key: " " }), { "aria-checked": "true", _preventDefault: true });
  assert.equal(handle(el({ "aria-checked": "false" }), { type: "keydown", key: "a" }), null); // non-toggle key
});
