// The honest-format public surface. The conformance runner and the tests import the API here, so the
// portable suite and the unit tests exercise the same surface. Built spoke by spoke from genX's
// fmtx/smartx (the reference of record); this increment carries the value coercions and the hf-type
// input conversion.
export { toNumber } from "./coerce.js";
export { convert } from "./convert.js";
export { format, bestDenominator } from "./format.js";
