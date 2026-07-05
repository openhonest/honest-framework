// apply() (honest-DOM spec §2.2): write a state object back to the DOM through a manifest. Like
// collect, the DOM read is injected as `query(selector) -> [elements]`, so apply is testable without a
// real DOM. Only entries that declare a write shortcut and whose key is present in the state are
// written, and the writer sets the property on every matching element. It never adds or removes
// elements. Used for page-refresh recovery, multi-tab sync, and optimistic rollback.
import { writeShortcut } from "./shortcuts.js";

export function apply(manifest, state, query) {
  for (const key of Object.keys(manifest)) {
    const entry = manifest[key];
    if (entry.write !== undefined && Object.hasOwn(state, key)) {
      const writer = writeShortcut(entry.write) ?? entry.write;
      for (const el of query(entry.selector)) {
        writer(el, state[key]);
      }
    }
  }
}
