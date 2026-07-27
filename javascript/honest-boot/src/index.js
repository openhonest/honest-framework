// honest-boot public surface (spec §4). The pure scan/read core plus the boundary steps (load, init,
// and the composed activate pass), the latter tested through injected plugs. The on-load / observer
// wiring (bootstrap) and the Playwright end-to-end suite land in the final pass.
export { buildSelector, resolvePrefix, neededModules, scan } from "./scan.js";
export { readConfig } from "./read.js";
export { parseVerbose, parseJson, parseColon, parseClass, parseMagic } from "./notation.js";
export { loadModules, initModule } from "./load.js";
export { activate } from "./activate.js";
export { boot } from "./boot.js";
