// Conformance for the self-describing notations (honest-boot spec §4 step 3, §10). Verbose (each
// prefix- attribute is a key) and JSON (a prefix-opts attribute is a config object) carry their own
// structure and need nothing from the vocabulary beyond the prefix. readConfig merges them and yields
// null when a resolved element has nothing to parse (so no empty classify is emitted). The colon and
// Type-Magic notations need a per-prefix slot structure that is not yet specified and are not built.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseVerbose, parseJson, readConfig } from "../src/index.js";

const VOCAB = { prefixes: { hf: "honest-format" }, attributes: { hf: ["hf-format"] }, classPrefixes: { fmt: "hf" }, values: {} };
const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("parseVerbose collects each prefix- attribute as a key, skipping -opts, -raw, and non-prefix attrs", () => {
  const element = el({ "hf-format": "currency", "hf-currency-code": "USD", "hf-opts": "{}", "hf-raw": "x", "data-y": "z" });
  assert.deepEqual(parseVerbose(element, "hf"), { format: "currency", "currency-code": "USD" });
});

test("parseJson reads the prefix-opts attribute as a config object, or {} when absent", () => {
  assert.deepEqual(parseJson(el({ "hf-opts": '{"decimals":2,"grouping":true}' }), "hf"), { decimals: 2, grouping: true });
  assert.deepEqual(parseJson(el({ "hf-format": "currency" }), "hf"), {});
});

test("readConfig merges the notations into one config, JSON overriding verbose", () => {
  const element = el({ "hf-format": "currency", "hf-decimals": "0", "hf-opts": '{"decimals":2}' });
  assert.deepEqual(readConfig(element, VOCAB), { module: "honest-format", config: { format: "currency", decimals: 2 } });
});

test("readConfig on an element with no honest attribute is null", () => {
  assert.equal(readConfig(el({ "data-x": "1" }), VOCAB), null);
});

test("readConfig on a resolved element with no parsed config is null", () => {
  assert.equal(readConfig(el({}, ["fmt-x"]), VOCAB), null);
});

test("readConfig guards a null prefix — a literal 'null-'-named attribute does not sneak through", () => {
  // resolvePrefix finds no honest prefix here; without the guard, verbose parsing under a coerced
  // "null" prefix would pick up a "null-foo" attribute as config. The guard is what prevents that.
  assert.equal(readConfig(el({ "null-foo": "bar" }), VOCAB), null);
});
