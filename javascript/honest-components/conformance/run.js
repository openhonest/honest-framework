// honest-components conformance runner. Reads the portable suite.json and checks each case against the
// public API: resolve the named function, apply it to the case's args, and deep-compare the result. The
// pure behaviours (toggled, handle) are language-agnostic input/output; enhance and scan need an event
// bus and a live element, so they are covered by the unit tests, not the portable suite. An element
// argument is a plain attribute object wrapped so getAttribute reads it. Data in, verdict out.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as components from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const suite = JSON.parse(readFileSync(join(here, "suite.json"), "utf8"));

// A case's first arg is an element's attributes; wrap it so the pure functions can read it.
const element = (attrs) => ({ getAttribute: (name) => (name in attrs ? attrs[name] : null) });

const results = suite.cases.map((testCase) => {
  const args = [element(testCase.element), ...(testCase.rest ?? [])];
  const actual = components[testCase.function](...args);
  const ok = JSON.stringify(actual) === JSON.stringify(testCase.expected);
  if (!ok) {
    console.log(`FAIL ${testCase.id}: got ${JSON.stringify(actual)}, expected ${JSON.stringify(testCase.expected)}`);
  }
  return ok;
});

const failed = results.filter((ok) => !ok).length;
console.log(`conformance: ${results.length - failed} passed, ${failed} failed, ${results.length} total`);
process.exit(failed === 0 ? 0 : 1);
