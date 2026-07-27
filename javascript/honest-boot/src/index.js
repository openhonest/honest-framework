// honest-boot public surface: the pure scan/read core (spec §4, steps 1-3). The boundary steps
// (load, init, observe, emit) land next, tested through injected plugs.
export { buildSelector, resolvePrefix, neededModules, scan } from "./scan.js";
export { readConfig } from "./read.js";
