// honest-boot: one activation pass over a root (spec §4, steps 4-7 composed). Scan the root for declared
// elements, load the fresh modules, init each against the root, and emit one classify event per resolved
// element. Every boundary is injected via deps — query (DOM read), importer (network), emit (observe
// sink) — and the already-loaded set is threaded through, so activate holds no hidden state. The real
// bootstrap calls this on load and again on each honest.bridge mutation (an HTMX swap).
import { scan } from "./scan.js";
import { readConfig } from "./read.js";
import { loadModules, initModule } from "./load.js";

export async function activate(root, deps) {
  const { elements, needed } = scan((selector) => deps.query(root, selector), deps.vocabulary);
  const { loaded, fresh } = await loadModules(needed, deps.importer, deps.loaded);
  for (const name of Object.keys(fresh)) {
    initModule(fresh[name], root);
  }
  for (const element of elements) {
    const config = readConfig(element, deps.vocabulary);
    if (config) deps.emit(element, config);
  }
  return loaded;
}
