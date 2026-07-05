// collect() (honest-DOM spec §2.1): read DOM state through a manifest, returning a plain object. The
// DOM read is injected as `query(selector) -> [elements]`, so collect is a pure function of its inputs
// and never reaches for a global; the boundary supplies the real document query. Every call reads
// fresh; nothing is cached, so the DOM stays the single authority on state (DATAOS).
import { readShortcut } from "./shortcuts.js";

// 0 elements -> null, 1 -> the scalar, 2+ -> the array (§2.1). Math.min collapses "many" to 2, so the
// cardinality selects the result through a table, not a length branch chain.
const COLLAPSE = {
  0: () => null,
  1: (values) => values[0],
  2: (values) => values,
};

export function collect(manifest, query) {
  const state = {};
  for (const key of Object.keys(manifest)) {
    const entry = manifest[key];
    const reader = readShortcut(entry.read) ?? entry.read;
    const values = query(entry.selector).map(reader);
    state[key] = COLLAPSE[Math.min(values.length, 2)](values);
  }
  return state;
}
