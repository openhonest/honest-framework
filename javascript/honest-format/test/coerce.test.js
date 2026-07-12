// Conformance for coerce (honest-format spec §6.2). toNumber reads a value to a number, or null when
// it does not parse — the single "not a number" signal the formatters fall back on.
import { test } from "node:test";
import assert from "node:assert/strict";
import { toNumber } from "../src/index.js";

test("a numeric string reads to its number", () => {
  assert.equal(toNumber("42.5"), 42.5);
  assert.equal(toNumber("915166064277"), 915166064277);
});

test("a plain number reads to itself", () => {
  assert.equal(toNumber(4250), 4250);
});

test("non-numeric text reads to null", () => {
  assert.equal(toNumber("abc"), null);
  assert.equal(toNumber(""), null);
});
