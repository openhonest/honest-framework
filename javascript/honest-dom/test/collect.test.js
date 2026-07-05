// Conformance for collect() (honest-DOM spec §2.1). collect reads DOM state through a manifest and an
// injected query: query(selector) returns the matching elements. The DOM read is the boundary, passed
// in, so collect is a pure function of (manifest, query) and needs no real DOM. Elements are plain
// objects. Zero matches -> null, one -> the scalar, many -> the array.
import { test } from "node:test";
import assert from "node:assert/strict";
import { collect } from "../src/index.js";

// A fake query: a table from selector to the elements it "matches".
const queryFrom = (matches) => (selector) => matches[selector] ?? [];

test("one match reads the scalar value", () => {
  const query = queryFrom({ "#name": [{ value: "Ada" }] });
  assert.deepEqual(collect({ name: { selector: "#name", read: "value" } }, query), { name: "Ada" });
});

test("zero matches map the key to null", () => {
  const query = queryFrom({});
  assert.deepEqual(collect({ name: { selector: "#missing", read: "value" } }, query), { name: null });
});

test("many matches map the key to the full array", () => {
  const query = queryFrom({ ".tag": [{ dataset: { tag: "a" } }, { dataset: { tag: "b" } }, { dataset: { tag: "c" } }] });
  assert.deepEqual(collect({ tags: { selector: ".tag", read: "data:tag" } }, query), { tags: ["a", "b", "c"] });
});

test("a custom function read is used directly", () => {
  const query = queryFrom({ "#el": [{ id: 7 }] });
  assert.deepEqual(collect({ n: { selector: "#el", read: (el) => el.id * 2 } }, query), { n: 14 });
});

test("multiple entries collect independently", () => {
  const query = queryFrom({ "#a": [{ value: "x" }], "#b": [{ checked: true }] });
  const manifest = { a: { selector: "#a", read: "value" }, b: { selector: "#b", read: "checked" } };
  assert.deepEqual(collect(manifest, query), { a: "x", b: true });
});
