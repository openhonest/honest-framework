// Conformance for observe/on (honest-DOM spec §2.3-2.4). The shared MutationObserver, the event
// delegation, and the rAF batching are the injected bus's: bus.onMutation(h) and bus.onEvent(type, h)
// subscribe and return an unsubscribe; bus.schedule(fn) batches. observe only picks the per-entry
// strategy (value -> input, checked -> change, watch override, else mutation) and wires the
// collect-and-callback through the bus, so it stays free of addEventListener and mutable batching state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { observe, on } from "../src/index.js";

const makeBus = () => {
  const subs = [];
  const scheduled = [];
  return {
    onMutation(handler) {
      const sub = { kind: "mutation", handler, active: true };
      subs.push(sub);
      return () => (sub.active = false);
    },
    onEvent(type, handler) {
      const sub = { kind: "event", type, handler, active: true };
      subs.push(sub);
      return () => (sub.active = false);
    },
    schedule(fn) {
      scheduled.push(fn);
      fn();
    },
    subs,
    scheduled,
  };
};

test("on subscribes the callback to raw mutations and returns the unsubscribe", () => {
  const bus = makeBus();
  const cb = () => {};
  const unsub = on(cb, bus);
  assert.equal(bus.subs.length, 1);
  assert.equal(bus.subs[0].kind, "mutation");
  assert.equal(bus.subs[0].handler, cb);
  unsub();
  assert.equal(bus.subs[0].active, false);
});

test("observe subscribes each entry by its read strategy", () => {
  const bus = makeBus();
  const manifest = {
    v: { selector: "#v", read: "value" },
    c: { selector: "#c", read: "checked" },
    t: { selector: "#t", read: "text" },
    w: { selector: "#w", read: "text", watch: "custom" },
  };
  observe(manifest, () => {}, bus, () => []);
  const strategy = bus.subs.map((s) => (s.kind === "event" ? s.type : "mutation"));
  assert.deepEqual(strategy, ["input", "change", "mutation", "custom"]);
});

test("observe fires the callback with fresh collected state via both the event and mutation branches", () => {
  const bus = makeBus();
  let got;
  const query = (sel) => (sel === "#v" ? [{ value: "hi" }] : sel === "#t" ? [{ textContent: "yo" }] : []);
  const manifest = { v: { selector: "#v", read: "value" }, t: { selector: "#t", read: "text" } };
  const unsub = observe(manifest, (state) => (got = state), bus, query);
  bus.subs[0].handler(); // the value entry, delegated to the input event
  assert.deepEqual(got, { v: "hi", t: "yo" });
  bus.subs[1].handler(); // the text entry, from the shared mutation observer
  assert.deepEqual(got, { v: "hi", t: "yo" });
  assert.equal(bus.scheduled.length, 2);
  unsub();
  assert.equal(bus.subs[0].active, false);
  assert.equal(bus.subs[1].active, false);
});
