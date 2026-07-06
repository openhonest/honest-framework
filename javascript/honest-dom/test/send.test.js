// Conformance for send/replay/clearCache (honest-DOM spec §2.5-2.7): the cache-and-replay pattern.
// The browser I/O is injected as deps: query (for collect), now (the clock), fetch, and the cache
// get/set/removeItem. deps.getItem returns a parsed object or null, so the malformed-and-null handling
// (which needs a try/catch) lives in the boundary and replay stays pure decision logic.
import { test } from "node:test";
import assert from "node:assert/strict";
import { send, replay, clearCache } from "../src/index.js";

const makeDeps = (over = {}) => {
  const store = {};
  return {
    query: (sel) => over.matches?.[sel] ?? [],
    now: () => over.now ?? 1000,
    fetch: over.fetch ?? ((url, init) => ({ url, init })),
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, obj) => (store[key] = obj),
    removeItem: (key) => delete store[key],
    store,
  };
};

test("send collects state, caches the request, and POSTs the state as JSON", () => {
  const deps = makeDeps({ matches: { "#q": [{ value: "hi" }] }, now: 5000 });
  const result = send("/api/search", { q: { selector: "#q", read: "value" } }, {}, deps);
  assert.deepEqual(deps.store["domx:lastRequest"], { url: "/api/search", state: { q: "hi" }, timestamp: 5000 });
  assert.equal(result.url, "/api/search");
  assert.equal(result.init.method, "POST");
  assert.equal(result.init.headers["Content-Type"], "application/json");
  assert.equal(result.init.body, JSON.stringify({ q: "hi" }));
});

test("clearCache removes the cached request", () => {
  const deps = makeDeps();
  deps.setItem("domx:lastRequest", { url: "/x" });
  clearCache(deps);
  assert.equal(deps.getItem("domx:lastRequest"), null);
});

test("replay returns null when there is no cached request", async () => {
  assert.equal(await replay(makeDeps()), null);
});

test("replay returns null when the cached request is one ms past the 5-minute ttl", async () => {
  const deps = makeDeps({ now: 300001 });
  deps.setItem("domx:lastRequest", { url: "/x", state: { a: 1 }, timestamp: 0 });
  assert.equal(await replay(deps), null);
});

test("replay re-POSTs a request exactly at the ttl edge", async () => {
  let called;
  const deps = makeDeps({ now: 300000, fetch: (url, init) => ((called = { url, init }), { ok: true }) });
  deps.setItem("domx:lastRequest", { url: "/api/search", state: { q: "hi" }, timestamp: 0 });
  const result = await replay(deps);
  assert.equal(called.url, "/api/search");
  assert.equal(called.init.method, "POST");
  assert.equal(called.init.headers["Content-Type"], "application/json");
  assert.equal(called.init.body, JSON.stringify({ q: "hi" }));
  assert.deepEqual(result, { ok: true });
});
