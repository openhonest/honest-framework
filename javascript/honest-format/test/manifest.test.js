// Conformance for the declared vocabulary manifest (honest-format spec §5.4, Level 2). MANIFEST is the
// data honest-check's HC-REF004 resolves authored hf-* values against, emitted from the implementation's
// dispatch tables. These exact-list assertions are the completeness contract: adding or removing a
// formatter, converter, or enumerated option without updating the vocabulary fails here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { MANIFEST } from "../src/index.js";

test("MANIFEST declares exactly the format vocabulary", () => {
  assert.deepEqual(MANIFEST.formats, [
    "abbreviated", "accounting", "billions", "capitalize", "compact", "creditcard", "currency", "date",
    "datetime", "duration", "filesize", "fraction", "lowercase", "millions", "number", "percent", "phone",
    "relative", "scientific", "smart", "ssn", "time", "trillions", "trim", "truncate", "uppercase",
  ]);
});

test("MANIFEST declares exactly the hf-type vocabulary", () => {
  assert.deepEqual(MANIFEST.inputTypes, [
    "auto", "b", "bool", "boolean", "bytes", "cents", "date", "decimal", "double", "epoch", "float",
    "fraction", "gb", "gigabytes", "hours", "hr", "int", "integer", "iso", "iso8601", "kb", "kilobytes",
    "mb", "megabytes", "milliseconds", "min", "minutes", "ms", "null", "number", "pennies", "percent",
    "percentage", "sec", "seconds", "str", "string", "text", "timestamp", "undefined", "unix",
  ]);
  // The JSON conversions are deferred to the bind boundary, so they are not yet declared.
  assert.ok(!MANIFEST.inputTypes.includes("json"));
});

test("MANIFEST declares the enumerated option values", () => {
  assert.deepEqual(MANIFEST.options["hf-phone-format"], ["intl", "us", "us-dash", "us-dot"]);
  assert.deepEqual(MANIFEST.options["hf-date-format"], ["custom", "full", "iso", "long", "medium", "short"]);
  assert.deepEqual(MANIFEST.options["hf-time-format"], ["long", "long-24", "medium", "medium-24", "short", "short-24"]);
  assert.deepEqual(MANIFEST.options["hf-duration-format"], ["clock", "compact", "human", "long", "medium", "short"]);
});

test("the emitted manifest.json is in sync with MANIFEST (regenerate with emit-manifest.mjs)", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const emitted = JSON.parse(readFileSync(join(here, "..", "manifest.json"), "utf8"));
  assert.deepEqual(emitted, MANIFEST);
});
