// Conformance for detect (honest-format spec §7.1). detect auto-detects a value's type by a
// confidence-scored pattern table; the highest score wins, ties keep the table order, and an empty or
// unmatched value is text. Every expected result is from the genX SmartX reference.
import { test } from "node:test";
import assert from "node:assert/strict";
import { detect } from "../src/index.js";

test("detect returns text for an empty value or no match", () => {
  assert.deepEqual(detect(""), { type: "text", confidence: 100 });
  assert.deepEqual(detect("hello"), { type: "text", confidence: 100 });
});

test("detect scores currency by symbol or word", () => {
  assert.deepEqual(detect("$1,234.56"), { type: "currency", confidence: 95 });
  assert.deepEqual(detect("£99"), { type: "currency", confidence: 95 });
  assert.deepEqual(detect("50 usd"), { type: "currency", confidence: 92 });
});

test("detect scores percentage, email, and url at full confidence", () => {
  assert.deepEqual(detect("50%"), { type: "percentage", confidence: 100 });
  assert.deepEqual(detect("user@example.com"), { type: "email", confidence: 100 });
  assert.deepEqual(detect("https://www.site.org/path"), { type: "url", confidence: 100 });
});

test("detect scores phone across its confidence tiers", () => {
  assert.deepEqual(detect("+1 555 123 4567"), { type: "phone", confidence: 95 });
  assert.deepEqual(detect("(555) 123-4567"), { type: "phone", confidence: 90 });
  assert.deepEqual(detect("5551234567"), { type: "phone", confidence: 85 });
  assert.deepEqual(detect("12345"), { type: "phone", confidence: 40 });
  assert.deepEqual(detect("123456789"), { type: "phone", confidence: 40 }); // nine digits, still below ten
  assert.deepEqual(detect("555-123-4567"), { type: "phone", confidence: 70 });
});

test("detect scores date across its confidence tiers", () => {
  assert.deepEqual(detect("2024-03-15"), { type: "date", confidence: 98 });
  assert.deepEqual(detect("March 5"), { type: "date", confidence: 95 });
  assert.deepEqual(detect("03/15/2024"), { type: "date", confidence: 90 });
  assert.deepEqual(detect("15-03-2024"), { type: "date", confidence: 75 });
});

test("detect scores number across its confidence tiers", () => {
  assert.deepEqual(detect("1,234"), { type: "number", confidence: 85 });
  assert.deepEqual(detect("123"), { type: "number", confidence: 50 });
  assert.deepEqual(detect("12.5"), { type: "number", confidence: 70 });
});

test("detect returns the highest-confidence match when several patterns match", () => {
  // "50" matches both phone (40) and number (50); the higher score wins (pins the sort direction).
  assert.deepEqual(detect("50"), { type: "number", confidence: 50 });
});
