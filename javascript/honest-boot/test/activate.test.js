// Conformance for activate (honest-boot spec §4, steps 4-7 composed): one pass over a root — scan for
// declared elements, load the fresh modules, init them against the root, and emit one classify event per
// resolved element. Every boundary is injected: query (the DOM read), importer (the network), emit (the
// observe sink). loaded is threaded in and returned, so activate holds no hidden state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { activate } from "../src/index.js";

const VOCAB = {
  prefixes: { hf: "honest-format", hd: "honest-drag" },
  attributes: { hf: ["hf-format"], hd: ["hd-draggable"] },
  classPrefixes: { fmt: "hf" },
  values: {},
};
const el = (attrs = {}, classes = []) => ({
  attributes: Object.keys(attrs).map((name) => ({ name })),
  classList: classes,
  getAttribute: (name) => (name in attrs ? attrs[name] : null),
});

test("activate scans, loads fresh modules, inits them, and emits per resolved element", async () => {
  const fmtEl = el({ "hf-format": "currency" });
  const dragEl = el({ "hd-draggable": "" });
  const classOnly = el({}, ["fmt-x"]); // resolves a prefix by class but carries no attribute value
  const els = [fmtEl, dragEl, classOnly];
  const inits = [];
  const importer = async (name) => ({ autoInit: (root) => inits.push([name, root]) });
  const emitted = [];
  const root = { id: "r" };
  const deps = {
    query: (queryRoot, selector) => (queryRoot === root ? els : []),
    vocabulary: VOCAB,
    importer,
    loaded: [],
    emit: (element, config) => emitted.push([element, config]),
  };

  const loaded = await activate(root, deps);

  assert.deepEqual(loaded, ["honest-drag", "honest-format"]);
  // needed is sorted, so fresh imports (and inits) run drag then format.
  assert.deepEqual(inits, [["honest-drag", root], ["honest-format", root]]);
  // one emit per element that resolves to a value; the class-only element carries none, so it is skipped.
  assert.deepEqual(emitted, [
    [fmtEl, { module: "honest-format", attribute: "hf-format", value: "currency" }],
    [dragEl, { module: "honest-drag", attribute: "hd-draggable", value: "" }],
  ]);
});

test("activate does not re-init a module already loaded", async () => {
  const els = [el({ "hf-format": "currency" })];
  const inits = [];
  const importer = async (name) => ({ autoInit: () => inits.push(name) });
  const deps = {
    query: () => els,
    vocabulary: VOCAB,
    importer,
    loaded: ["honest-format"],
    emit: () => {},
  };
  const loaded = await activate({ id: "r" }, deps);
  assert.deepEqual(loaded, ["honest-format"]);
  assert.deepEqual(inits, []); // already loaded -> nothing fresh -> no init
});
