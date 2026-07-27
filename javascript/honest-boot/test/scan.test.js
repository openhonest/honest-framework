// Conformance for the scan core (honest-boot spec §4, steps 1-2). Every step is pure: the DOM read is
// an injected query(selector) -> elements, exactly as honest-DOM's collect injects its query, so no
// real DOM is needed. Elements are plain objects carrying `attributes` (name list), `classList`, and
// `getAttribute`. The declared vocabulary is passed in — it is the source of truth (§3).
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildSelector, resolvePrefix, neededModules, scan } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format", hd: "honest-drag" },
  attributes: { hf: ["hf-format"], hd: ["hd-draggable"] },
  classPrefixes: { fmt: "hf" },
  values: { "hf-format": ["currency", "date"] },
};

// A plain-object element: an attribute name→value map, plus optional class names.
const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("buildSelector covers every declared attribute and class prefix", () => {
  assert.equal(buildSelector(VOCAB), '[hf-format],[hd-draggable],[class*="fmt-"]');
});

test("resolvePrefix reads a declared honest attribute", () => {
  assert.equal(resolvePrefix(el({ "hf-format": "currency" }), VOCAB), "hf");
});

test("resolvePrefix reads a declared class notation", () => {
  assert.equal(resolvePrefix(el({}, ["fmt-currency"]), VOCAB), "hf");
});

test("resolvePrefix ignores an undeclared attribute (no hx- collision)", () => {
  assert.equal(resolvePrefix(el({ "hx-get": "/x", "data-y": "1" }), VOCAB), null);
});

test("resolvePrefix ignores a non-honest class", () => {
  assert.equal(resolvePrefix(el({}, ["btn", "card"]), VOCAB), null);
});

test("neededModules returns the owning modules, sorted, deduped", () => {
  const els = [el({ "hf-format": "currency" }), el({ "hd-draggable": "" }), el({ "hf-format": "date" })];
  assert.deepEqual(neededModules(els, VOCAB), ["honest-drag", "honest-format"]);
});

test("scan queries the built selector and reports elements and needed modules", () => {
  const els = [el({ "hf-format": "currency" }), el({ "hd-draggable": "" })];
  const query = (selector) => (selector === buildSelector(VOCAB) ? els : []);
  assert.deepEqual(scan(query, VOCAB), { elements: els, needed: ["honest-drag", "honest-format"] });
});
