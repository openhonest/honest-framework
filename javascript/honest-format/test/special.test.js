// Conformance for the structured formats (honest-format spec §5.1). phone, ssn, and creditcard operate
// on the string's digits; compact is abbreviated-without-suffix (genX's Intl compact notation is invalid
// and always fell back). Every expected string is from the genX reference.
import { test } from "node:test";
import assert from "node:assert/strict";
import { format } from "../src/index.js";

test("phone formats ten domestic digits in each style", () => {
  assert.equal(format("phone", "5551234567"), "(555) 123-4567"); // default us
  assert.equal(format("phone", "5551234567", { phoneFormat: "us-dash" }), "555-123-4567");
  assert.equal(format("phone", "5551234567", { phoneFormat: "us-dot" }), "555.123.4567");
  assert.equal(format("phone", "5551234567", { phoneFormat: "intl" }), "+1 555 123 4567");
  assert.equal(format("phone", "15551234567"), "(555) 123-4567"); // 11 digits, leading 1 stripped
  assert.equal(format("phone", "25551234567"), "25551234567"); // 11 digits, NOT leading 1 -> not stripped, unchanged
  assert.equal(format("phone", "12345"), "12345"); // not ten digits -> unchanged
  assert.equal(format("phone", "5551234567", { phoneFormat: "bogus" }), "5551234567"); // unknown style -> unchanged
});

test("phone handles an international-format input", () => {
  assert.equal(format("phone", "+1 555 123 4567"), "(555) 123-4567"); // +1 US reformatted to the us style
  assert.equal(format("phone", "+1 555 123 4567", { phoneFormat: "us-dash" }), "555-123-4567");
  assert.equal(format("phone", "+1 555 123 4567", { phoneFormat: "us-dot" }), "555.123.4567");
  assert.equal(format("phone", "+1 555 123 4567", { phoneFormat: "intl" }), "+1 555 123 4567"); // intl style -> normalized, not reformatted
  assert.equal(format("phone", "+2 555 123 4567", { phoneFormat: "us" }), "+2 555 123 4567"); // 11 digits but not +1 -> normalized, not US-reformatted
  assert.equal(format("phone", "+1 555 12"), "+1 555 12"); // +1 but not eleven digits -> normalized
  assert.equal(format("phone", "+44 20 7946 0958"), "+44 20 7946 0958"); // non-US -> normalized
  assert.equal(format("phone", "0044 20 7946 0958"), "+44 20 7946 0958"); // 00 prefix -> +
  assert.equal(format("phone", "+44  20   7946"), "+44 20 7946"); // extra whitespace collapsed
});

test("ssn masks by default and reveals under mask:false", () => {
  assert.equal(format("ssn", "123456789"), "***-**-6789");
  assert.equal(format("ssn", "123456789", { mask: false }), "123-45-6789");
  assert.equal(format("ssn", "12345"), "12345"); // not nine digits -> unchanged
});

test("creditcard masks by default and groups under mask:false", () => {
  assert.equal(format("creditcard", "4111111111111111"), "****-****-****-1111");
  assert.equal(format("creditcard", "4111111111111111", { mask: false }), "4111-1111-1111-1111");
  assert.equal(format("creditcard", "411111111111"), "****-****-****-1111"); // twelve digits, the minimum
  assert.equal(format("creditcard", "12345678901"), "12345678901"); // eleven digits, one below the minimum -> unchanged
  assert.equal(format("creditcard", "1234567"), "1234567"); // fewer than twelve digits -> unchanged
});

test("compact is abbreviated without a suffix; the long option has no effect", () => {
  assert.equal(format("compact", "1500"), "1.5K");
  assert.equal(format("compact", "1500000"), "1.5M");
  assert.equal(format("compact", "1234567890"), "1.2B");
  assert.equal(format("compact", "1500000", { long: true }), "1.5M"); // long is inert (genX's compact bug, reproduced)
  assert.equal(format("compact", "abc"), "abc"); // numeric guard: unparseable -> string form
});
