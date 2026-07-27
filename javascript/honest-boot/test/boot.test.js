// Conformance for boot (honest-boot spec §4, step 6): the lifecycle orchestrator — one activation on
// start, then re-activation whenever the shared observer (honest.bridge) reports a change, scoped to the
// changed subtree (an HTMX swap). The observer subscription is injected, so boot is unit-testable with a
// stand-in subscribe; the real browser wiring lives in the composition root (the page), covered by the
// Playwright suite.
import { test } from "node:test";
import assert from "node:assert/strict";
import { boot } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format" },
  attributes: { hf: ["hf-format"] },
  classPrefixes: {},
  values: {},
};
const el = (value) => ({
  attributes: [{ name: "hf-format" }],
  classList: [],
  getAttribute: (name) => (name === "hf-format" ? value : null),
});

test("boot activates once on start and re-activates on each observer event", async () => {
  const byTarget = { root: [el("currency")], swap: [el("date")] };
  const emitted = [];
  let observerCb;
  const deps = {
    query: (target) => byTarget[target] ?? [],
    vocabulary: VOCAB,
    importer: async () => ({ autoInit: () => {} }),
    loaded: [],
    emit: (_element, config) => emitted.push(config.config.format),
    subscribe: (cb) => {
      observerCb = cb;
    },
  };

  await boot("root", deps);
  assert.deepEqual(emitted, ["currency"]); // initial pass processed the root

  await observerCb("swap");
  assert.deepEqual(emitted, ["currency", "date"]); // the observer event re-activated on the swapped subtree
});
