// Conformance for the switch behaviour (honest-components §2.4). The behaviour is pure over the DOM and
// an injected event bus, so it is exercised over plain element mocks and a fake bus — no real DOM, no
// addEventListener. State is the element's aria-checked attribute (DATAOS); handle is pure; enhance wires
// through the bus and returns an unsubscribe; scan enhances by the DOM-visible processed marker.
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyChanges, enhance, handle, scan, toggled } from "../src/index.js";

// A DOM-like element mock: attributes over a store.
const el = (attrs = {}) => {
  const store = { ...attrs };
  return {
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, v) => { store[name] = String(v); },
    _store: store,
  };
};

// A fake bus: onEvent(el, type, handler) records the subscription and returns an unsubscribe; fire()
// delivers an event to the matching handlers.
const makeBus = () => {
  const subs = [];
  return {
    subs,
    onEvent(element, type, handler) {
      const sub = { element, type, handler, active: true };
      subs.push(sub);
      return () => { sub.active = false; };
    },
    fire(element, event) {
      for (const sub of subs) {
        if (sub.active && sub.element === element && sub.type === event.type) {
          sub.handler(event);
        }
      }
    },
  };
};

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

test("applyChanges writes only changed attributes, skips the marker, and no-ops on null", () => {
  const target = el({ "aria-checked": "false" });
  applyChanges(target, { "aria-checked": "true", _preventDefault: true });
  assert.equal(target.getAttribute("aria-checked"), "true");
  assert.equal(target.getAttribute("_preventDefault"), null); // the marker is not written as an attribute
  const same = el({ "aria-checked": "true" });
  same.setAttribute = () => { throw new Error("should not write an unchanged attribute"); };
  applyChanges(same, { "aria-checked": "true", _preventDefault: false }); // unchanged -> no write
  applyChanges(same, null); // null -> no-op
});

test("enhance wires the switch through the bus, toggling on click and preventing the key default", () => {
  const bus = makeBus();
  const target = el({ "aria-checked": "false" });
  const prevented = [];
  const unsubscribe = enhance(target, bus);
  assert.equal(bus.subs.length, 2); // one per event type

  bus.fire(target, { type: "click", preventDefault: () => prevented.push("click") });
  assert.equal(target.getAttribute("aria-checked"), "true");
  assert.deepEqual(prevented, []); // a click default is not prevented

  bus.fire(target, { type: "keydown", key: "Enter", preventDefault: () => prevented.push("key") });
  assert.equal(target.getAttribute("aria-checked"), "false");
  assert.deepEqual(prevented, ["key"]); // a toggle key's default is prevented

  bus.fire(target, { type: "keydown", key: "a", preventDefault: () => prevented.push("no") });
  assert.equal(target.getAttribute("aria-checked"), "false"); // non-toggle key -> unchanged
  assert.deepEqual(prevented, ["key"]); // and its default not prevented

  unsubscribe();
  assert.deepEqual(bus.subs.map((s) => s.active), [false, false]); // every subscription torn down
});

test("scan enhances each unenhanced switch, marks it, and skips a marked one", () => {
  const bus = makeBus();
  const fresh = el({ "hc-switch": "", "aria-checked": "false" });
  const done = el({ "hc-switch": "", "hc-enhanced": "", "aria-checked": "false" });
  const other = el({ "aria-checked": "false" }); // no hc-switch
  const root = { querySelectorAll: (selector) => (selector === "[hc-switch]" ? [fresh, done, other].filter((e) => "hc-switch" in e._store) : []) };

  const unsubscribes = scan(root, bus);
  assert.equal(unsubscribes.length, 1); // only the fresh switch enhanced
  assert.equal(fresh.getAttribute("hc-enhanced"), ""); // marked
  assert.equal(bus.subs.length, 2); // the fresh switch's two subscriptions, not the already-enhanced one

  bus.fire(fresh, { type: "click", preventDefault: () => {} });
  assert.equal(fresh.getAttribute("aria-checked"), "true"); // the fresh switch is live
});
