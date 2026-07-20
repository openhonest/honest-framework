// Conformance for the shared enhancement runtime (honest-components §2.4). applyChanges, enhance, and
// scan are the capability every interactive component composes, exercised here over plain element mocks,
// a fake bus, and a minimal sample component (its events and a pure handle) — no real DOM, no
// addEventListener.
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyChanges, enhance, scan } from "../src/index.js";

// A DOM-like element mock: attributes over a store.
const el = (attrs = {}) => {
  const store = { ...attrs };
  return {
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, v) => { store[name] = String(v); },
    _store: store,
  };
};

// A fake bus: onEvent records the subscription and returns an unsubscribe; fire delivers an event.
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

// A minimal sample component: the events it listens on and a pure handle that toggles aria-checked,
// preventing the default on an Enter keydown and no-opping on any other key.
const EVENTS = ["click", "keydown"];
const handle = (target, event) => {
  if (event.type === "keydown" && event.key !== "Enter") {
    return null;
  }
  return { "aria-checked": String(target.getAttribute("aria-checked") !== "true"), _preventDefault: event.type === "keydown" };
};

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

test("enhance wires an element through the bus, applying changes and preventing the key default", () => {
  const bus = makeBus();
  const target = el({ "aria-checked": "false" });
  const prevented = [];
  const unsubscribe = enhance(target, bus, EVENTS, handle);
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

test("scan enhances each unenhanced element matching the selector, marks it, and skips a marked one", () => {
  const bus = makeBus();
  const fresh = el({ "hc-sample": "", "aria-checked": "false" });
  const done = el({ "hc-sample": "", "hc-enhanced": "", "aria-checked": "false" });
  const other = el({ "aria-checked": "false" }); // no hc-sample
  const root = { querySelectorAll: (selector) => (selector === "[hc-sample]" ? [fresh, done, other].filter((e) => "hc-sample" in e._store) : []) };

  const unsubscribes = scan(root, bus, "[hc-sample]", EVENTS, handle);
  assert.equal(unsubscribes.length, 1); // only the fresh element enhanced
  assert.equal(fresh.getAttribute("hc-enhanced"), ""); // marked
  assert.equal(bus.subs.length, 2); // the fresh element's two subscriptions, not the already-enhanced one

  bus.fire(fresh, { type: "click", preventDefault: () => {} });
  assert.equal(fresh.getAttribute("aria-checked"), "true"); // the fresh element is live
});
