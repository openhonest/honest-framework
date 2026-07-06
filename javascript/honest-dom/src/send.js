// send / replay / clearCache (honest-DOM spec §2.5-2.7): the cache-and-replay pattern honest-DOM owns.
// The browser I/O is injected as deps so these stay pure orchestration: query (for collect), now (the
// clock), fetch, and the cache getItem/setItem/removeItem. deps.getItem returns a parsed object or
// null, so the localStorage read, JSON.parse, and the malformed-and-null handling (which needs a
// try/catch) live in the boundary; replay is left as pure decision logic. honest-DOM owns the cache
// key and the time-to-live; the boundary owns the storage.
import { collect } from "./collect.js";

const CACHE_KEY = "domx:lastRequest";
const CACHE_TTL_MS = 300000; // 5 minutes

export function send(url, manifest, opts, deps) {
  const state = collect(manifest, deps.query);
  deps.setItem(CACHE_KEY, { url, state, timestamp: deps.now() });
  return deps.fetch(url, { ...opts, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state) });
}

export async function replay(deps) {
  const entry = deps.getItem(CACHE_KEY);
  if (entry === null) {
    return null;
  }
  if (deps.now() - entry.timestamp > CACHE_TTL_MS) {
    return null;
  }
  return deps.fetch(entry.url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(entry.state) });
}

export function clearCache(deps) {
  deps.removeItem(CACHE_KEY);
}
