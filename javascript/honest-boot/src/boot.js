// honest-boot: the lifecycle orchestrator (spec §4, step 6). Activate once on start, then re-activate on
// each shared-observer event, scoped to the changed subtree (an HTMX swap). The observer subscription is
// injected (honest.bridge in the browser), so boot holds no hidden state and is unit-testable with a
// stand-in subscribe; the real browser wiring — the observer, the DOM query, dynamic import, the emit
// sink — lives in the composition root (the page) and is covered by the Playwright suite.
import { activate } from "./activate.js";

export function boot(root, deps) {
  deps.subscribe((target) => activate(target, deps));
  return activate(root, deps);
}
