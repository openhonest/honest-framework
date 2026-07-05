// Conformance for apply() (honest-DOM spec §2.2). apply writes a state object back to the DOM through
// a manifest and an injected query. Only entries with a write shortcut and a key present in the state
// are written; the writer sets the property on every matching element. The query is the boundary,
// passed in, so apply is testable with plain-object elements and no real DOM.
import { test } from "node:test";
import assert from "node:assert/strict";
import { apply } from "../src/index.js";

const queryFrom = (matches) => (selector) => matches[selector] ?? [];

test("writes the state value to every matching element", () => {
  const one = {};
  const two = {};
  const query = queryFrom({ ".name": [one, two] });
  apply({ name: { selector: ".name", write: "value" } }, { name: "Ada" }, query);
  assert.equal(one.value, "Ada");
  assert.equal(two.value, "Ada");
});

test("an entry without a write shortcut is skipped", () => {
  const el = {};
  const query = queryFrom({ "#read-only": [el] });
  apply({ ro: { selector: "#read-only", read: "value" } }, { ro: "x" }, query);
  assert.equal(el.value, undefined);
});

test("a key absent from the state is skipped (partial application)", () => {
  const el = {};
  const query = queryFrom({ "#a": [el] });
  apply({ a: { selector: "#a", write: "value" } }, {}, query);
  assert.equal(el.value, undefined);
});

test("a custom function write is used directly", () => {
  const el = { dataset: {} };
  const query = queryFrom({ "#el": [el] });
  apply({ n: { selector: "#el", write: (e, v) => (e.dataset.n = String(v)) } }, { n: 7 }, query);
  assert.equal(el.dataset.n, "7");
});
