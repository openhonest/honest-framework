// Conformance for the read-shortcut resolver (honest-DOM spec §2.1). Each read shortcut maps to a
// pure extractor over a DOM-like element; the element is a plain object here, so no DOM is needed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readShortcut } from "../src/shortcuts.js";

test("value shortcut reads el.value", () => {
  assert.equal(readShortcut("value")({ value: "hi" }), "hi");
});

test("checked shortcut reads el.checked", () => {
  assert.equal(readShortcut("checked")({ checked: true }), true);
});

test("text shortcut reads el.textContent", () => {
  assert.equal(readShortcut("text")({ textContent: "body" }), "body");
});

test("attr:name shortcut reads the named attribute", () => {
  assert.equal(readShortcut("attr:href")({ getAttribute: (n) => `[${n}]` }), "[href]");
});

test("data:name shortcut reads the named dataset entry", () => {
  assert.equal(readShortcut("data:tag")({ dataset: { tag: "urgent" } }), "urgent");
});
