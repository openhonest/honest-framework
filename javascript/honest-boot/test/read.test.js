// Conformance for read (honest-boot spec §4, step 3). read resolves a declared attribute into the
// config handed to the owning module — a lookup against the declared vocabulary, not a classification.
// The value is something the developer declared from a closed vocabulary, so read never types unknown
// input; validity of the declared value is honest-check's pre-commit concern, not a runtime re-check.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readConfig } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format", hd: "honest-drag" },
  attributes: { hf: ["hf-format"], hd: ["hd-draggable"] },
  classPrefixes: { fmt: "hf" },
  values: { "hf-format": ["currency", "date"] },
};

const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("readConfig resolves a declared attribute to its module, attribute, and value", () => {
  assert.deepEqual(readConfig(el({ "hf-format": "currency" }), VOCAB), {
    module: "honest-format",
    attribute: "hf-format",
    value: "currency",
  });
});

test("readConfig on an element with no honest attribute is null", () => {
  assert.equal(readConfig(el({ "data-x": "1" }), VOCAB), null);
});

test("readConfig on a class-notation element carrying no attribute value is null", () => {
  // The class resolves a prefix, but there is no hf-format attribute to read a value from.
  assert.equal(readConfig(el({}, ["fmt-currency"]), VOCAB), null);
});
