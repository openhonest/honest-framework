// honest-format conformance runner. Reads the portable suite.json and checks each case against the
// public API: resolve the named function, apply it to the case's args, and deep-compare the result.
// Data in, verdict out — the JavaScript counterpart of run_conformance.py. Lives outside src/, so it is
// harness tooling, not part of the honest-check / coverage surface.
//
//   node javascript/honest-format/conformance/run.js
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as honestFormat from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const suite = JSON.parse(readFileSync(join(here, "suite.json"), "utf8"));

const results = suite.cases.map((testCase) => {
  const actual = honestFormat[testCase.function](...testCase.args);
  const ok = JSON.stringify(actual) === JSON.stringify(testCase.expected);
  if (!ok) {
    console.log(`FAIL ${testCase.id}: got ${JSON.stringify(actual)}, expected ${JSON.stringify(testCase.expected)}`);
  }
  return ok;
});

const failed = results.filter((ok) => !ok).length;
console.log(`conformance: ${results.length - failed} passed, ${failed} failed, ${results.length} total`);
process.exit(failed === 0 ? 0 : 1);
