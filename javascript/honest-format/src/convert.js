// convert (honest-format spec §5.2, §6.1): apply an hf-type input conversion to a raw value before it
// is formatted — cents to dollars, a Unix timestamp to a Date, kilobytes to bytes. The conversion is
// selected from a table by name; an unknown or absent name is the identity, so convert is total over
// every input. Pure: the same value and name give the same result, with no DOM and no clock.
import { toNumber } from "./coerce.js";

// The words a boolean conversion reads as false. Only the false-words need naming: they are truthy
// strings ("false", "no", "off", "0" are all non-empty), so without this set they would wrongly read as
// true. The true-words genX also lists are inert — every one is a truthy string that Boolean() already
// reads as true — so they are not carried (behaviour is identical; the mutation gate proves the set is
// load-bearing where kept). Data, not code.
const _FALSE = new Set(["false", "0", "no", "off"]);

// The distinct conversion behaviours, keyed by a canonical name. Each is a pure arrow of
// (str, value) — the value's string form, and the original value for the fallbacks that need it. Arrows
// are anonymous table values, so they are not function points.
const _CONVERTERS = {
  number: (str) => toNumber(str),
  cents: (str) => toNumber(str) / 100,
  minutes: (str) => toNumber(str) * 60,
  hours: (str) => toNumber(str) * 3600,
  kilobytes: (str) => toNumber(str) * 1000,
  megabytes: (str) => toNumber(str) * 1e6,
  gigabytes: (str) => toNumber(str) * 1e9,
  integer: (str) => Math.floor(toNumber(str)),
  date: (str) => new Date(str),
  unix: (str) => new Date(toNumber(str) * 1000),
  milliseconds: (str) => new Date(toNumber(str)),
  string: (str) => str,
  boolean: (str, value) => {
    const lower = str.toLowerCase().trim();
    return _FALSE.has(lower) ? false : Boolean(value);
  },
  null: () => null,
  undefined: () => undefined,
};
// The JSON input conversions (object/obj/json, array/arr) parse untrusted attribute text, which is a
// boundary operation (a parse failure is data, not an exception raised through pure code). They are
// handled where the attribute is read — the bind boundary (§8) — not here, and land with that spoke.

// Every hf-type name maps to one of the canonical behaviours above. Aliases share a behaviour through
// this data table, so no conversion arrow is written twice.
const _ALIAS = {
  decimal: "number", fraction: "number", percentage: "number", percent: "number",
  float: "number", double: "number", seconds: "number", sec: "number", bytes: "number", b: "number",
  pennies: "cents",
  min: "minutes", hr: "hours",
  kb: "kilobytes", mb: "megabytes", gb: "gigabytes",
  int: "integer",
  iso: "date", iso8601: "date",
  timestamp: "unix", epoch: "unix",
  ms: "milliseconds",
  text: "string", str: "string",
  bool: "boolean",
};

export function convert(value, inputType) {
  // No type is the identity. The guard is load-bearing (not redundant with the fallthrough below): the
  // converter table carries "null" and "undefined" keys, so an absent inputType would otherwise collide
  // with the "undefined" converter. "auto" and any unknown name need no guard — they miss the table and
  // fall through to the identity return.
  if (!inputType) {
    return value;
  }
  const converter = _CONVERTERS[_ALIAS[inputType] ?? inputType];
  return converter === undefined ? value : converter(String(value), value);
}
