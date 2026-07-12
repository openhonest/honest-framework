// Conformance for the temporal formats (honest-format spec §5.1, §6.4). date/time/datetime render
// through the platform Intl API, so this file pins the timezone to UTC for deterministic output (each
// test file runs in its own process); every expected string is captured from the genX reference under
// the same TZ. relative is pure arithmetic against an injected `now` (§6.4: no clock read in the core).
process.env.TZ = "UTC";
import { test } from "node:test";
import assert from "node:assert/strict";
import { format, formatCustomDate } from "../src/index.js";

const DAY = "2024-03-15"; // a Friday

test("date renders each named style, iso, and a custom pattern", () => {
  assert.equal(format("date", DAY), "3/15/2024"); // short (default)
  assert.equal(format("date", DAY, { dateFormat: "medium" }), "Mar 15, 2024");
  assert.equal(format("date", DAY, { dateFormat: "long" }), "March 15, 2024");
  assert.equal(format("date", DAY, { dateFormat: "full" }), "Friday, March 15, 2024");
  assert.equal(format("date", DAY, { dateFormat: "iso" }), "2024-03-15");
  assert.equal(format("date", DAY, { dateFormat: "custom", pattern: "YYYY/MM/DD" }), "2024/03/15");
  assert.equal(format("date", DAY, { dateFormat: "bogus" }), "3/15/2024"); // unknown style -> short
  assert.equal(format("date", DAY, { format: "medium" }), "Mar 15, 2024"); // the `format` option alias
  assert.equal(format("date", DAY, { dateFormat: "custom" }), "3/15/2024"); // custom without a pattern -> short
  assert.equal(format("date", "not-a-date"), "not-a-date"); // unparseable -> string form
});

test("date resolves a Date produced by an hf-type conversion", () => {
  assert.equal(format("date", "0", { type: "unix", dateFormat: "iso" }), "1970-01-01");
});

test("formatCustomDate replaces every token against the date's components", () => {
  const d = new Date("2024-03-05T09:07:03Z");
  assert.equal(formatCustomDate(d, "YYYY-MM-DD HH:mm:ss"), "2024-03-05 09:07:03");
  assert.equal(formatCustomDate(d, "YY/M/D H:m:s"), "24/3/5 9:7:3"); // one-digit tokens, after the two-digit ones
});

test("datetime renders locale date and time", () => {
  assert.equal(format("datetime", "2024-03-15T14:30:00Z"), "3/15/2024, 2:30:00 PM");
});

test("time renders each style and honours the 24-hour and hour12 controls", () => {
  const T = "2024-03-15T14:30:45Z";
  assert.equal(format("time", T), "2:30 PM"); // short (default)
  assert.equal(format("time", T, { timeFormat: "medium" }), "2:30:45 PM");
  assert.equal(format("time", T, { timeFormat: "long" }), "2:30:45 PM UTC");
  assert.equal(format("time", T, { timeFormat: "short-24" }), "14:30");
  assert.equal(format("time", T, { timeFormat: "medium-24" }), "14:30:45");
  assert.equal(format("time", T, { timeFormat: "long-24" }), "14:30:45 UTC");
  assert.equal(format("time", T, { timeFormat: "bogus" }), "2:30 PM"); // unknown style -> short
  assert.equal(format("time", "14:30:00"), "2:30 PM"); // a bare time of day
  assert.equal(format("time", "14:30:00", { hour12: false }), "14:30"); // hour12 disabled
  assert.equal(format("time", "not-a-time"), "not-a-time"); // neither a date nor a time -> string form
});

const NOW = new Date("2024-03-15T12:00:00Z");
const ago = (seconds) => new Date(NOW.getTime() - seconds * 1000).toISOString();
const hence = (seconds) => new Date(NOW.getTime() + seconds * 1000).toISOString();
const rel = (iso) => format("relative", iso, { now: NOW });

test("relative renders past distances across every unit, singular and plural", () => {
  assert.equal(rel(ago(30)), "just now");
  assert.equal(rel(ago(60)), "1 minute ago");
  assert.equal(rel(ago(300)), "5 minutes ago");
  assert.equal(rel(ago(3600)), "1 hour ago");
  assert.equal(rel(ago(7200)), "2 hours ago");
  assert.equal(rel(ago(86400)), "1 day ago");
  assert.equal(rel(ago(259200)), "3 days ago");
  assert.equal(rel(ago(604800)), "1 week ago");
  assert.equal(rel(ago(1209600)), "2 weeks ago");
  assert.equal(rel(ago(2592000)), "1 month ago");
  assert.equal(rel(ago(5184000)), "2 months ago");
  assert.equal(rel(ago(31536000)), "1 year ago");
  assert.equal(rel(ago(63072000)), "2 years ago");
});

test("relative renders future distances across every unit, singular and plural", () => {
  assert.equal(rel(hence(30)), "in a moment");
  assert.equal(rel(hence(60)), "in 1 minute");
  assert.equal(rel(hence(300)), "in 5 minutes");
  assert.equal(rel(hence(3600)), "in 1 hour");
  assert.equal(rel(hence(7200)), "in 2 hours");
  assert.equal(rel(hence(86400)), "in 1 day");
  assert.equal(rel(hence(172800)), "in 2 days");
});

test("relative tier boundaries pin every threshold and per-unit divisor (mutation adequacy)", () => {
  // just-below each past-tier max, and the per-unit divisor via a value that floors to 1 only at the
  // right divisor.
  assert.equal(rel(ago(0)), "just now"); // diffSec exactly 0 -> past, not future
  assert.equal(rel(ago(59)), "just now"); // just below 60
  assert.equal(rel(ago(118)), "1 minute ago"); // minute per=60 (118/60 = 1, /59 = 2)
  assert.equal(rel(ago(3599)), "59 minutes ago"); // just below 3600
  assert.equal(rel(ago(7199)), "1 hour ago"); // hour per=3600
  assert.equal(rel(ago(86399)), "23 hours ago"); // just below 86400
  assert.equal(rel(ago(172799)), "1 day ago"); // day per=86400
  assert.equal(rel(ago(604799)), "6 days ago"); // just below 604800
  assert.equal(rel(ago(1209599)), "1 week ago"); // week per=604800
  assert.equal(rel(ago(2419199)), "3 weeks ago"); // just below 2419200
  assert.equal(rel(ago(2419200)), "0 month ago"); // exactly the week/month boundary
  assert.equal(rel(ago(5183999)), "1 month ago"); // month per=2592000
  assert.equal(rel(ago(31103999)), "11 months ago"); // just below 31104000
  assert.equal(rel(ago(31104000)), "0 year ago"); // exactly the month/year boundary
  assert.equal(rel(ago(63071999)), "1 year ago"); // year divisor 31536000
  // the ms->seconds divisor: 59999 ms floors to 59 s, not 60
  assert.equal(format("relative", new Date(NOW.getTime() - 59999).toISOString(), { now: NOW }), "just now");
  // future-tier boundaries and per-unit divisors
  assert.equal(rel(hence(1)), "in a moment"); // diffSec -1: future, below a minute
  assert.equal(rel(hence(59)), "in a moment"); // just below 60
  assert.equal(rel(hence(118)), "in 1 minute"); // minute per
  assert.equal(rel(hence(3599)), "in 59 minutes"); // just below 3600
  assert.equal(rel(hence(7199)), "in 1 hour"); // hour per
  assert.equal(rel(hence(86399)), "in 23 hours"); // just below 86400
  assert.equal(rel(hence(172799)), "in 1 day"); // day per
});

test("datetime and relative fall back to the string form for an unparseable value", () => {
  assert.equal(format("datetime", "not-a-date"), "not-a-date");
  assert.equal(format("relative", "not-a-date", { now: NOW }), "not-a-date");
});

test("time distinguishes 2-digit from numeric on a single-digit hour", () => {
  const T = "2024-03-15T09:05:03Z";
  assert.equal(format("time", T, { timeFormat: "short-24" }), "09:05"); // 2-digit, vs numeric "9:05"
  assert.equal(format("time", T, { timeFormat: "medium-24" }), "09:05:03");
  assert.equal(format("time", T, { timeFormat: "long-24" }), "09:05:03 UTC");
  assert.equal(format("time", T), "9:05 AM"); // numeric short
});
