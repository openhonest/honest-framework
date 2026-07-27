// honest-boot: load and init a module (spec §4, steps 4-5). Both take their I/O as an injected plug —
// importer(name) -> module is the dynamic import (the boundary), and the module's own autoInit/init does
// the DOM work — so the logic here is pure over them and needs no real network or DOM. loadModules holds
// no hidden cache: the already-loaded names are threaded in and the updated set returned.

export async function loadModules(needed, importer, alreadyLoaded) {
  const loaded = new Set(alreadyLoaded);
  const fresh = {};
  for (const name of needed) {
    if (!loaded.has(name)) {
      fresh[name] = await importer(name);
      loaded.add(name);
    }
  }
  return { loaded: [...loaded].sort(), fresh };
}

export function initModule(module, root) {
  if (module.autoInit) return module.autoInit(root);
  if (module.init) return module.init();
  return null;
}
