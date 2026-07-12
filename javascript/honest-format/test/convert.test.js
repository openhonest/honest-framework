// Conformance for convert (honest-format spec §5.2, §6.1). convert applies an hf-type conversion before
// formatting; an unknown or absent type is the identity. Pure. Ground truth for the currency/percent
// paths is the genX reference (e.g. cents of "4250" formats as "$42.50", so the conversion is 42.5).
import { test } from "node:test";
import assert from "node:assert/strict";
import { convert } from "../src/index.js";

test("an absent or auto type passes the value through unchanged", () => {
  assert.equal(convert("x"), "x"); // !inputType (undefined)
  assert.equal(convert("x", ""), "x"); // !inputType (empty)
  assert.equal(convert("x", "auto"), "x"); // === "auto"
});

test("an unknown type passes the value through unchanged", () => {
  assert.equal(convert("5", "bogus"), "5");
});

test("numeric conversions parse and scale", () => {
  assert.equal(convert("42", "number"), 42);
  assert.equal(convert("4250", "cents"), 42.5);
  assert.equal(convert("2", "minutes"), 120);
  assert.equal(convert("2", "hours"), 7200);
  assert.equal(convert("2", "kilobytes"), 2000);
  assert.equal(convert("2", "megabytes"), 2000000);
  assert.equal(convert("2", "gigabytes"), 2000000000);
  assert.equal(convert("3.9", "integer"), 3);
});

test("every number-behaviour alias parses like number", () => {
  // Each alias is load-bearing: convert(alias) must give the canonical result, so a mutated alias entry
  // (renamed key or emptied target) is caught.
  for (const alias of ["decimal", "fraction", "percentage", "percent", "float", "double", "seconds", "sec", "bytes", "b"]) {
    assert.equal(convert("7", alias), 7, alias);
  }
});

test("every scale-behaviour alias resolves to its canonical conversion", () => {
  assert.equal(convert("4250", "pennies"), 42.5); // -> cents
  assert.equal(convert("2", "min"), 120); // -> minutes
  assert.equal(convert("2", "hr"), 7200); // -> hours
  assert.equal(convert("2", "kb"), 2000); // -> kilobytes
  assert.equal(convert("2", "mb"), 2000000); // -> megabytes
  assert.equal(convert("2", "gb"), 2000000000); // -> gigabytes
  assert.equal(convert("3.9", "int"), 3); // -> integer
});

test("string conversion and its aliases return the string form", () => {
  // Non-string inputs, so the conversion is observable (String(7) differs from the raw 7 the fallthrough
  // would return): this is what makes each string alias load-bearing.
  assert.equal(convert(42, "string"), "42");
  assert.equal(convert(7, "text"), "7"); // alias -> string
  assert.equal(convert(9, "str"), "9"); // alias -> string
});

test("date conversions and aliases build a Date, faithfully raw for an unparseable value", () => {
  assert.equal(convert("2024-03-15", "date").getTime(), new Date("2024-03-15").getTime());
  assert.equal(convert("2024-03-15", "iso").getTime(), new Date("2024-03-15").getTime()); // -> date
  assert.equal(convert("2024-03-15", "iso8601").getTime(), new Date("2024-03-15").getTime()); // -> date
  assert.equal(convert("1710518400", "unix").getTime(), 1710518400 * 1000);
  assert.equal(convert("1710518400", "timestamp").getTime(), 1710518400 * 1000); // -> unix
  assert.equal(convert("1710518400", "epoch").getTime(), 1710518400 * 1000); // -> unix
  assert.equal(convert("1710518400000", "milliseconds").getTime(), 1710518400000);
  assert.equal(convert("1710518400000", "ms").getTime(), 1710518400000); // -> milliseconds
  assert.ok(Number.isNaN(convert("nope", "date").getTime()));
});

test("boolean conversion forces false-words to false, else reads truthiness", () => {
  assert.equal(convert("false", "boolean"), false);
  assert.equal(convert("0", "boolean"), false);
  assert.equal(convert("no", "boolean"), false);
  assert.equal(convert("off", "bool"), false); // alias -> boolean
  assert.equal(convert("yes", "boolean"), true); // truthy string, not a false-word
  assert.equal(convert("", "boolean"), false); // falsy string
});

test("null and undefined conversions produce those values", () => {
  assert.equal(convert("x", "null"), null);
  assert.equal(convert("x", "undefined"), undefined);
});
