// Emit the declared hf-* vocabulary (src/manifest.js) to manifest.json — the build artifact honest-check
// reads for HC-REF004 (spec §5.4). Regenerate after any change to the format/convert vocabulary:
//
//   node javascript/honest-format/emit-manifest.mjs
//
// Tooling, outside src/; the manifest.test.js drift check fails the gate if manifest.json is stale.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { MANIFEST } from "./src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
writeFileSync(join(here, "manifest.json"), `${JSON.stringify(MANIFEST, null, 2)}\n`);
