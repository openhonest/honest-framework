// Conformance for Type Magic (honest-boot spec §10). The bare-prefix attribute (hf="currency USD 2")
// carries unordered tokens; each goes to the first slot whose declared recognizer accepts it. Recognizers
// are each module's declared surface — a closed value-set (format) or a coercion kind (integer for
// decimals). A slot with no declared recognizer (currency, an open Intl string) is unplaceable by design,
// so its token is dropped, not guessed. Pure over a plain-object element.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseMagic, readConfig } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format" },
  attributes: { hf: ["hf-format"] },
  classPrefixes: { fmt: "hf" },
  slots: { hf: ["format", "currency", "decimals"] },
  recognizers: {
    hf: {
      format: { kind: "set", set: ["currency", "date", "number", "percent"] },
      currency: { kind: "currency" },
      decimals: { kind: "integer" },
    },
  },
  values: {},
};
const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("parseMagic places each token in the slot whose recognizer accepts it, regardless of order", () => {
  assert.deepEqual(parseMagic(el({ hf: "2 currency" }), "hf", VOCAB), { decimals: "2", format: "currency" });
});

test("parseMagic places a currency token via the Intl currency recognizer", () => {
  // With the currency slot declaring the currency recognizer, "USD" (an ISO-4217 code) is placed.
  assert.deepEqual(parseMagic(el({ hf: "currency USD 2" }), "hf", VOCAB), { format: "currency", currency: "USD", decimals: "2" });
});

test("parseMagic drops a token no recognizer accepts (not a currency, not an integer, not in the set)", () => {
  // "zzz" is none of: a format name, an ISO-4217 currency, or an integer — so it is dropped, not guessed.
  assert.deepEqual(parseMagic(el({ hf: "currency zzz 2" }), "hf", VOCAB), { format: "currency", decimals: "2" });
});

test("parseMagic fills each slot at most once", () => {
  // Two integer-looking tokens; only the first fills decimals.
  assert.deepEqual(parseMagic(el({ hf: "3 5" }), "hf", VOCAB), { decimals: "3" });
});

test("parseMagic returns {} when there is no bare-prefix attribute", () => {
  assert.deepEqual(parseMagic(el({ "hf-format": "currency" }), "hf", VOCAB), {});
});

test("parseMagic returns {} when the prefix declares no slots or recognizers", () => {
  assert.deepEqual(parseMagic(el({ hf: "currency 2" }), "hf", { prefixes: { hf: "honest-format" } }), {});
});

test("readConfig composes Type Magic — including the currency slot — into the module config", () => {
  assert.deepEqual(readConfig(el({ hf: "currency USD 2" }), VOCAB), {
    module: "honest-format",
    config: { format: "currency", currency: "USD", decimals: "2" },
  });
});
