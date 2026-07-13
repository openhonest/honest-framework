// Conformance for the DOM boundary (honest-format spec §8). scan/formatElement/unformatElement and the
// readSource/readOptions/writeDisplay helpers reach the DOM only through an element's own methods and an
// injected `now`, so they are exercised over plain element mocks — no real DOM, and `now` is fixed so a
// relative format is deterministic. The formatted strings trace to the format() conformance (genX).
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatElement, readOptions, readSource, scan, unformatElement, writeDisplay } from "../src/index.js";

// A DOM-like element mock: attributes over a store, plus mutable text/value and a tagName.
const el = (attrs = {}, { text = "", value = "", tag = "SPAN" } = {}) => {
  const store = { ...attrs };
  return {
    tagName: tag,
    textContent: text,
    value,
    getAttribute: (name) => (name in store ? store[name] : null),
    setAttribute: (name, v) => { store[name] = String(v); },
  };
};

const NOW = new Date("2024-03-15T12:00:00Z");
const ago = (seconds) => new Date(NOW.getTime() - seconds * 1000).toISOString();

test("readSource prefers hf-raw, then hf-value, then text, then an input value", () => {
  assert.equal(readSource(el({ "hf-raw": "1299.99", "hf-value": "x" }, { text: "y" })), "1299.99");
  assert.equal(readSource(el({ "hf-value": "42" }, { text: "y" })), "42");
  assert.equal(readSource(el({}, { text: "  hi  " })), "hi");
  assert.equal(readSource(el({}, { text: "", value: "v", tag: "INPUT" })), "v");
  assert.equal(readSource(el({}, { text: "" })), "");
});

test("readOptions reads and coerces every hf-* option attribute", () => {
  // Every option attribute, so each key mapping and each int/bool/string coercion is pinned; hf-length
  // "19" also pins the parseInt radix (base 9 or 11 would give 1 or 20).
  const opts = readOptions(el({
    "hf-type": "cents", "hf-decimals": "2", "hf-locale": "en-GB", "hf-currency": "EUR",
    "hf-thousands": "false", "hf-factor": "false", "hf-prefix": "$", "hf-suffix": "!",
    "hf-threshold": "2000", "hf-denominator": "4", "hf-length": "19", "hf-pattern": "YYYY",
    "hf-phone-format": "us", "hf-date-format": "iso", "hf-time-format": "short-24",
    "hf-duration-format": "clock", "hf-binary": "true", "hf-mask": "false", "hf-hour12": "true",
  }));
  assert.deepEqual(opts, {
    type: "cents", decimals: 2, locale: "en-GB", currency: "EUR",
    thousands: false, factor: false, prefix: "$", suffix: "!",
    threshold: 2000, denominator: 4, length: 19, pattern: "YYYY",
    phoneFormat: "us", dateFormat: "iso", timeFormat: "short-24",
    durationFormat: "clock", binary: true, mask: false, hour12: true,
  });
  assert.deepEqual(readOptions(el({})), {}); // no hf-* attributes -> no options
});

test("writeDisplay writes only on a change, to the value or the text", () => {
  const span = el({}, { text: "old" });
  writeDisplay(span, "new");
  assert.equal(span.textContent, "new");
  writeDisplay(span, "new"); // unchanged -> no rewrite
  assert.equal(span.textContent, "new");
  const input = el({}, { value: "old", tag: "INPUT" });
  writeDisplay(input, "new"); // an input writes value, not text
  assert.equal(input.value, "new");
  writeDisplay(input, "new"); // unchanged -> no rewrite
  assert.equal(input.value, "new");
  const area = el({}, { value: "old", text: "keep-text", tag: "TEXTAREA" });
  writeDisplay(area, "new"); // a textarea writes value; the text is left alone
  assert.equal(area.value, "new");
  assert.equal(area.textContent, "keep-text");
});

test("formatElement reads, formats, writes, and records the source", () => {
  const span = el({ "hf-format": "currency" }, { text: "1299.99" });
  formatElement(span, NOW);
  assert.equal(span.textContent, "$1,299.99");
  assert.equal(span.getAttribute("hf-raw"), "1299.99"); // recorded

  const withOpts = el({ "hf-format": "number", "hf-decimals": "0" }, { text: "1234.5" });
  formatElement(withOpts, NOW);
  assert.equal(withOpts.textContent, "1,235");
});

test("formatElement delegates a smart format to detection", () => {
  const span = el({ "hf-format": "smart" }, { text: "5551234567" });
  formatElement(span, NOW);
  assert.equal(span.textContent, "(555) 123-4567"); // detected phone, then formatted as phone
});

test("formatElement reads the injected now for a relative format", () => {
  const span = el({ "hf-format": "relative" }, { text: ago(300) });
  formatElement(span, NOW);
  assert.equal(span.textContent, "5 minutes ago");
});

test("formatElement leaves a non-hf-format element untouched", () => {
  const span = el({}, { text: "x" });
  formatElement(span, NOW);
  assert.equal(span.textContent, "x");
  assert.equal(span.getAttribute("hf-raw"), null);
});

test("formatElement re-formats from the recorded source without re-recording it", () => {
  const span = el({ "hf-format": "currency", "hf-raw": "1299.99", "hf-decimals": "0" }, { text: "$1,299.99" });
  formatElement(span, NOW);
  assert.equal(span.textContent, "$1,300"); // re-formatted from hf-raw with the new decimals
  assert.equal(span.getAttribute("hf-raw"), "1299.99"); // unchanged
});

test("formatElement leaves a present hf-raw in place, even an empty one", () => {
  const span = el({ "hf-format": "currency", "hf-raw": "", "hf-value": "42" }, { text: "" });
  formatElement(span, NOW);
  assert.equal(span.textContent, "$42.00"); // sourced from hf-value (an empty hf-raw is falsy)
  assert.equal(span.getAttribute("hf-raw"), ""); // present -> not overwritten
});

test("unformatElement restores the recorded source, or nothing when unformatted", () => {
  const formatted = el({ "hf-format": "currency", "hf-raw": "1299.99" }, { text: "$1,299.99" });
  assert.equal(unformatElement(formatted), "1299.99");
  assert.equal(formatted.textContent, "1299.99");
  const plain = el({ "hf-format": "currency" }, { text: "x" });
  assert.equal(unformatElement(plain), null);
  assert.equal(plain.textContent, "x");
});

test("scan formats every unprocessed element and skips a processed one", () => {
  const fresh = el({ "hf-format": "currency" }, { text: "1299.99" });
  // A processed element whose display does NOT match its source, so skipping vs re-formatting is visible.
  const done = el({ "hf-format": "currency", "hf-raw": "50" }, { text: "stale" });
  const root = { querySelectorAll: (selector) => (selector === "[hf-format]" ? [fresh, done] : []) };
  scan(root, NOW);
  assert.equal(fresh.textContent, "$1,299.99");
  assert.equal(fresh.getAttribute("hf-raw"), "1299.99");
  assert.equal(done.textContent, "stale"); // already processed -> skipped, not re-formatted to $50.00
});
