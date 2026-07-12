// Conformance for format (honest-format spec §5.1, §6). format renders a value under a named format;
// every expected string here is the output of the genX reference (the reference of record), captured by
// running its fmtx `format`. Pure — no clock, so temporal formats are not in this spoke.
import { test } from "node:test";
import assert from "node:assert/strict";
import { format, bestDenominator } from "../src/index.js";

test("format dispatches, guards numeric parse, and falls back on the unknown", () => {
  assert.equal(format("unknownFormat", "hello"), "hello"); // unknown format -> string form
  assert.equal(format("number", "abc"), "abc"); // numeric format, unparseable -> string form
  assert.equal(format("uppercase", "abc"), "ABC"); // non-numeric format needs no number
});

test("number groups and fixes decimals", () => {
  assert.equal(format("number", "1234.5"), "1,234.50");
  assert.equal(format("number", "1234.5", { decimals: 0 }), "1,235");
  assert.equal(format("number", "1234.5", { thousands: false }), "1234.50");
});

test("currency uses the currency and decimals options", () => {
  assert.equal(format("currency", "1299.99"), "$1,299.99");
  assert.equal(format("currency", "1299.99", { currency: "EUR" }), "€1,299.99");
  assert.equal(format("currency", "1299.9", { decimals: 0 }), "$1,300");
});

test("percent scales by 100 unless already a percentage, honouring factor and decimals", () => {
  assert.equal(format("percent", "0.1567"), "16%"); // default 0 decimals
  assert.equal(format("percent", "0.1567", { decimals: 2 }), "15.67%");
  assert.equal(format("percent", "15.67", { type: "percentage", decimals: 2 }), "15.67%"); // already percent -> factor 1
  assert.equal(format("percent", "15", { factor: false }), "15%"); // factor disabled -> no *100
});

test("scientific and accounting", () => {
  assert.equal(format("scientific", "12345"), "1.23e+4");
  assert.equal(format("scientific", "12345", { decimals: 3 }), "1.235e+4");
  assert.equal(format("accounting", "1234.5"), "$1,234.50");
  assert.equal(format("accounting", "-1234.5"), "($1,234.50)"); // negatives parenthesised
  assert.equal(format("accounting", "1234.5", { locale: "en-US", currency: "EUR" }), "€1,234.50"); // explicit locale + currency
});

test("an explicit locale is honoured", () => {
  // Cover the locale-provided side of each locale-defaulting format (output matches en-US default).
  assert.equal(format("number", "1234.5", { locale: "en-US" }), "1,234.50");
  assert.equal(format("currency", "1299.99", { locale: "en-US" }), "$1,299.99");
});

test("percent reads the 'percent' input type as already-scaled", () => {
  assert.equal(format("percent", "15.67", { type: "percent", decimals: 2 }), "15.67%");
});

test("abbreviated buckets by magnitude with threshold, decimals, prefix and suffix", () => {
  assert.equal(format("abbreviated", "1234"), "1.2K");
  assert.equal(format("abbreviated", "1234567"), "1.2M");
  assert.equal(format("abbreviated", "1234567890"), "1.2B");
  assert.equal(format("abbreviated", "1234567890123"), "1.2T");
  assert.equal(format("abbreviated", "500"), "500.0"); // below the default threshold -> plain
  assert.equal(format("abbreviated", "1500", { threshold: 2000 }), "1500.0"); // below a custom threshold
  assert.equal(format("abbreviated", "915166064277", { decimals: 2, prefix: "$" }), "$915.17B");
  assert.equal(format("abbreviated", "1500", { suffix: "!" }), "1.5K!");
});

test("millions, billions, trillions scale to their unit with prefix and optional suffix", () => {
  assert.equal(format("millions", "5000000"), "5.00M");
  assert.equal(format("billions", "5000000000"), "5.00B");
  assert.equal(format("trillions", "5000000000000"), "5.00T");
  assert.equal(format("millions", "5000000", { suffix: false }), "5.00"); // suffix suppressed
  assert.equal(format("millions", "5000000", { prefix: "~" }), "~5.00M");
  assert.equal(format("millions", "5000000", { decimals: 1 }), "5.0M"); // explicit decimals
  assert.equal(format("billions", "5000000000", { prefix: "~", decimals: 1, suffix: false }), "~5.0"); // all options
  assert.equal(format("trillions", "5000000000000", { prefix: "~", decimals: 1, suffix: false }), "~5.0");
});

test("filesize scales decimal or binary, with a zero guard", () => {
  assert.equal(format("filesize", "0"), "0 B");
  assert.equal(format("filesize", "1073741824"), "1.07 GB");
  assert.equal(format("filesize", "1048576", { binary: true }), "1.00 MiB");
  assert.equal(format("filesize", "1500"), "1.50 KB");
  assert.equal(format("filesize", "1073741824", { decimals: 1 }), "1.1 GB"); // explicit decimals
});

test("duration renders each style and its aliases over days/hours/minutes/seconds", () => {
  assert.equal(format("duration", "0"), "0s"); // all zero -> the seconds part
  assert.equal(format("duration", "3661"), "1h 1m 1s"); // short (default), no days
  assert.equal(format("duration", "90061"), "1d 1h 1m 1s"); // short with days
  assert.equal(format("duration", "60"), "1m"); // minutes only, no trailing 0s
  assert.equal(format("duration", "3661", { durationFormat: "human" }), "1h 1m 1s"); // alias -> short
  assert.equal(format("duration", "45", { durationFormat: "medium" }), "45 sec");
  assert.equal(format("duration", "90061", { durationFormat: "medium" }), "1 day 1 hr 1 min 1 sec"); // day singular
  assert.equal(format("duration", "176521", { durationFormat: "medium" }), "2 days 1 hr 2 min 1 sec"); // days plural
  assert.equal(format("duration", "0", { durationFormat: "medium" }), "0 sec"); // all zero -> the seconds part
  assert.equal(format("duration", "60", { durationFormat: "medium" }), "1 min"); // seconds zero but minutes present
  assert.equal(format("duration", "90061", { durationFormat: "long" }), "1 day, 1 hour, 1 minute, 1 second"); // singulars
  assert.equal(format("duration", "180122", { durationFormat: "long" }), "2 days, 2 hours, 2 minutes, 2 seconds"); // plurals
  assert.equal(format("duration", "0", { durationFormat: "long" }), "0 seconds");
  assert.equal(format("duration", "60", { durationFormat: "long" }), "1 minute"); // seconds zero but minutes present
  assert.equal(format("duration", "3661", { durationFormat: "clock" }), "01:01:01"); // no days
  assert.equal(format("duration", "90061", { durationFormat: "clock" }), "1:01:01:01"); // with days
  assert.equal(format("duration", "3661", { durationFormat: "compact" }), "01:01:01"); // alias -> clock
  assert.equal(format("duration", "3661", { durationFormat: "bogus" }), "01:01:01"); // unknown -> clock
});

test("fraction renders whole, proper, and mixed with a chosen or best denominator", () => {
  assert.equal(format("fraction", "1.5"), "1 1/2"); // mixed
  assert.equal(format("fraction", "2"), "2"); // whole (remainder 0)
  assert.equal(format("fraction", "0.25"), "1/4"); // proper (whole 0)
  assert.equal(format("fraction", "1.5", { denominator: 4 }), "1 2/4"); // chosen denominator
  assert.equal(format("fraction", "0.333"), "21/64"); // best denominator falls back to 64
});

test("text formats transform the string form", () => {
  assert.equal(format("uppercase", "Hello"), "HELLO");
  assert.equal(format("lowercase", "Hello"), "hello");
  assert.equal(format("capitalize", "hello world"), "Hello World");
  assert.equal(format("trim", "  hi  "), "hi");
  assert.equal(format("truncate", "the quick brown fox", { length: 9 }), "the qu...");
  assert.equal(format("truncate", "short", { length: 9 }), "short"); // under length -> unchanged
  assert.equal(format("truncate", "abcdefghij", { length: 5, suffix: "*" }), "abcd*");
  assert.equal(format("truncate", "short"), "short"); // default length of 50, under it -> unchanged
});

test("bestDenominator returns the coarsest matching power of two, up to the guaranteed 64", () => {
  assert.equal(bestDenominator(0.5), 2);
  assert.equal(bestDenominator(0.25), 4);
  assert.equal(bestDenominator(0.125), 8);
  assert.equal(bestDenominator(0.0625), 16);
  assert.equal(bestDenominator(0.03125), 32);
  assert.equal(bestDenominator(0.333), 64); // no coarser grid within a hundredth -> the fallback
  assert.equal(bestDenominator(0.51), 64); // error exactly 0.01 at the coarse grids must not match (strict <)
});

test("boundary and precision cases pin the numeric constants (mutation adequacy)", () => {
  assert.equal(format("accounting", "0"), "$0.00"); // sign boundary at zero
  assert.equal(format("accounting", "-0.5"), "($0.50)"); // a value in [-1, 0): the sign test's zero, not one
  // abbreviated: exact bucket boundaries, just-below each bucket, and the K threshold and divisor
  assert.equal(format("abbreviated", "1000000"), "1.0M");
  assert.equal(format("abbreviated", "1000000000"), "1.0B");
  assert.equal(format("abbreviated", "1000000000000"), "1.0T");
  assert.equal(format("abbreviated", "999999"), "1000.0K");
  assert.equal(format("abbreviated", "999999999"), "1000.0M");
  assert.equal(format("abbreviated", "999999999999"), "1000.0B");
  assert.equal(format("abbreviated", "1000"), "1.0K");
  assert.equal(format("abbreviated", "999"), "999.0");
  assert.equal(format("abbreviated", "1050"), "1.1K"); // K divisor: /1000 vs /1001
  assert.equal(format("abbreviated", "1949"), "1.9K"); // K divisor: /1000 vs /999
  // number/currency fraction-digit precision (min and max)
  assert.equal(format("number", "1234.567"), "1,234.57"); // max fraction digits
  assert.equal(format("currency", "1299.999"), "$1,300.00"); // max fraction digits
  assert.equal(format("currency", "1299.9"), "$1,299.90"); // min fraction digits
  // filesize: each decimal and binary unit (unit ladder members) and the two bases
  assert.equal(format("filesize", "500"), "500.00 B");
  assert.equal(format("filesize", "1500000"), "1.50 MB");
  assert.equal(format("filesize", "1500000000000"), "1.50 TB");
  assert.equal(format("filesize", "1500000000000000"), "1.50 PB");
  assert.equal(format("filesize", "500", { binary: true }), "500.00 B");
  assert.equal(format("filesize", "1500", { binary: true }), "1.46 KiB");
  assert.equal(format("filesize", "1073741824", { binary: true }), "1.00 GiB");
  assert.equal(format("filesize", "1200000000000", { binary: true }), "1.09 TiB");
  assert.equal(format("filesize", "1200000000000000", { binary: true }), "1.07 PiB");
  // duration: day/hour/minute divisors and their %-remainders
  assert.equal(format("duration", "86400"), "1d");
  assert.equal(format("duration", "86399"), "23h 59m 59s");
  assert.equal(format("duration", "90000"), "1d 1h");
  assert.equal(format("duration", "89999"), "1d 59m 59s");
  assert.equal(format("duration", "3600"), "1h");
  assert.equal(format("duration", "3599"), "59m 59s");
  assert.equal(format("duration", "3659"), "1h 59s");
  assert.equal(format("duration", "118"), "1m 58s");
  assert.equal(format("duration", "120"), "2m");
  // millions/billions divisor: only a value where the ±1 perturbation flips the second decimal pins the
  // exact power (1e6 / 1e9). trillions' ±1 is below double precision for every safe integer (declared).
  assert.equal(format("millions", "5000010000"), "5000.01M");
  assert.equal(format("billions", "5003691199996309"), "5003691.20B");
  // truncate: string length exactly at the limit is unchanged; the default length of 50 is pinned by a
  // 50-char string (unchanged) and a 51-char string (truncated to 47 + the suffix).
  assert.equal(format("truncate", "abcde", { length: 5 }), "abcde");
  assert.equal(format("truncate", "a".repeat(50)), "a".repeat(50));
  assert.equal(format("truncate", "a".repeat(51)), "a".repeat(47) + "...");
  // every numeric format renders an unparseable value as its own string (the _NUMERIC guard set)
  for (const type of ["currency", "percent", "scientific", "accounting", "abbreviated", "millions", "billions", "trillions", "filesize", "duration", "fraction"]) {
    assert.equal(format(type, "xyz"), "xyz", type);
  }
});
