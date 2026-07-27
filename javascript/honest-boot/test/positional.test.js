// Conformance for the positional notations (honest-boot spec §4 step 3, §10). Colon and class map
// positional tokens to a per-prefix ordered slot list declared in the vocabulary (the cardinality
// order, declared as data — genX's CARDINALITY_ORDERS, the HC-REF004 pattern). Colon splits the type
// attribute's value on ":"; class splits the class token (after its class prefix) on "-". Both zip
// tokens to slots in order, dropping any token past the last slot. Pure over a plain-object element.
// Type Magic (unordered tokens) needs per-slot recognition and is not here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseColon, parseClass, readConfig } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format" },
  attributes: { hf: ["hf-format"] },
  classPrefixes: { fmt: "hf" },
  slots: { hf: ["format", "currency", "decimals"] },
  values: {},
};
const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("parseColon splits the type value and zips it to the slots", () => {
  assert.deepEqual(parseColon(el({ "hf-format": "currency:USD:2" }), "hf", VOCAB), { format: "currency", currency: "USD", decimals: "2" });
});

test("parseColon zips fewer tokens than slots, and drops tokens past the last slot", () => {
  assert.deepEqual(parseColon(el({ "hf-format": "currency:USD" }), "hf", VOCAB), { format: "currency", currency: "USD" });
  assert.deepEqual(parseColon(el({ "hf-format": "currency:USD:2:extra" }), "hf", VOCAB), { format: "currency", currency: "USD", decimals: "2" });
});

test("parseColon returns {} with no slots, no attribute, or no colon", () => {
  assert.deepEqual(parseColon(el({ "hf-format": "a:b" }), "hf", { ...VOCAB, slots: undefined }), {});
  assert.deepEqual(parseColon(el({}), "hf", VOCAB), {});
  assert.deepEqual(parseColon(el({ "hf-format": "currency" }), "hf", VOCAB), {});
});

test("parseClass splits the class token after its prefix and zips it to the slots", () => {
  assert.deepEqual(parseClass(el({}, ["btn", "fmt-currency-USD-2"]), "hf", VOCAB), { format: "currency", currency: "USD", decimals: "2" });
});

test("parseClass returns {} with no slots, no mapping class prefix, or no matching class", () => {
  assert.deepEqual(parseClass(el({}, ["fmt-x"]), "hf", { ...VOCAB, slots: undefined }), {});
  assert.deepEqual(parseClass(el({}, ["fmt-x"]), "hf", { ...VOCAB, classPrefixes: {} }), {});
  assert.deepEqual(parseClass(el({}, ["btn"]), "hf", VOCAB), {});
});

test("parseClass guards an unmapped prefix — a literal 'undefined-' class does not sneak through", () => {
  // With no class prefix mapping to hf, classPrefix is undefined; without the guard a class literally
  // named "undefined-foo" would match the coerced "undefined-" and slip through. The guard prevents it.
  assert.deepEqual(parseClass(el({}, ["undefined-foo"]), "hf", { ...VOCAB, classPrefixes: {} }), {});
});

test("readConfig composes the positional notations into the module config", () => {
  assert.deepEqual(readConfig(el({ "hf-format": "currency:USD:2" }), VOCAB), {
    module: "honest-format",
    config: { format: "currency", currency: "USD", decimals: "2" },
  });
});
