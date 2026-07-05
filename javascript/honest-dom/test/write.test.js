// Conformance for the write-shortcut resolver (honest-DOM spec §2.2). Each write shortcut maps to a
// pure writer over a DOM-like element; the element is a plain object here, so no DOM is needed. The
// writer sets a property of the element it is given and touches nothing else.
import { test } from "node:test";
import assert from "node:assert/strict";
import { writeShortcut } from "../src/index.js";

test("value shortcut writes el.value", () => {
  const el = {};
  writeShortcut("value")(el, "hi");
  assert.equal(el.value, "hi");
});

test("checked shortcut writes el.checked", () => {
  const el = {};
  writeShortcut("checked")(el, true);
  assert.equal(el.checked, true);
});

test("text shortcut writes el.textContent", () => {
  const el = {};
  writeShortcut("text")(el, "body");
  assert.equal(el.textContent, "body");
});

test("attr:name shortcut sets the named attribute", () => {
  const written = {};
  const el = { setAttribute: (n, v) => (written[n] = v) };
  writeShortcut("attr:href")(el, "/x");
  assert.equal(written.href, "/x");
});

test("data:name shortcut sets the named dataset entry", () => {
  const el = { dataset: {} };
  writeShortcut("data:tag")(el, "urgent");
  assert.equal(el.dataset.tag, "urgent");
});
