// Conformance for the load/init boundary (honest-boot spec §4, steps 4-5). The network import and the
// module's own init are injected — importer(name) -> module is the boundary, so loadModules is pure over
// it and needs no real dynamic import. loadModules imports only what is not already loaded; initModule
// prefers the DATAOS autoInit (read state from the DOM) over a plain init.
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadModules, initModule } from "../src/index.js";

test("loadModules imports each needed module once and reports what is fresh", async () => {
  const calls = [];
  const importer = async (name) => {
    calls.push(name);
    return { name };
  };
  const result = await loadModules(["honest-drag", "honest-format"], importer, []);
  assert.deepEqual(result.loaded, ["honest-drag", "honest-format"]);
  assert.deepEqual(result.fresh, { "honest-drag": { name: "honest-drag" }, "honest-format": { name: "honest-format" } });
  assert.deepEqual(calls, ["honest-drag", "honest-format"]);
});

test("loadModules skips a module already loaded and does not re-import it", async () => {
  const calls = [];
  const importer = async (name) => {
    calls.push(name);
    return { name };
  };
  const result = await loadModules(["honest-format"], importer, ["honest-format"]);
  assert.deepEqual(result.fresh, {});
  assert.deepEqual(result.loaded, ["honest-format"]);
  assert.deepEqual(calls, []);
});

test("loadModules imports a repeated need only once", async () => {
  const calls = [];
  const importer = async (name) => {
    calls.push(name);
    return { name };
  };
  const result = await loadModules(["honest-format", "honest-format"], importer, []);
  assert.deepEqual(calls, ["honest-format"]);
  assert.deepEqual(result.loaded, ["honest-format"]);
});

const ROOT = { id: "root" };

test("initModule prefers autoInit, passing the root (DATAOS)", () => {
  const module = { autoInit: (root) => ({ via: "autoInit", root }) };
  assert.deepEqual(initModule(module, ROOT), { via: "autoInit", root: ROOT });
});

test("initModule falls back to init when there is no autoInit", () => {
  const module = { init: () => ({ via: "init" }) };
  assert.deepEqual(initModule(module, ROOT), { via: "init" });
});

test("initModule returns null when the module exposes neither", () => {
  assert.equal(initModule({}, ROOT), null);
});
