// The CSS namespace contract (honest-components §6, style.js). scopeCss scopes an organism's own selectors
// under its BEM block while leaving already-namespaced, global, and group at-rule preludes alone;
// tokenContractViolations enforces the style.json <-> CSS token bijection; mergeTokenContracts collects
// every component's tokens and fails loudly on a duplicate. All three are pure text/value transforms.
import { test } from "node:test";
import assert from "node:assert/strict";
import { scopeCss, tokenContractViolations, mergeTokenContracts } from "../src/index.js";

test("scopeCss prefixes an unnamespaced selector with the block", () => {
  assert.equal(scopeCss(".row { color: red }", "data-table"), ".data-table .row { color: red }");
});

test("scopeCss leaves an already-namespaced selector untouched", () => {
  assert.equal(scopeCss(".data-table__row { x: 1 }", "data-table"), ".data-table__row { x: 1 }");
});

test("scopeCss leaves the global element, universal, and :root selectors untouched", () => {
  assert.equal(scopeCss("html { x: 1 }", "data-table"), "html { x: 1 }");
  assert.equal(scopeCss("* { x: 1 }", "data-table"), "* { x: 1 }");
  assert.equal(scopeCss(":root { x: 1 }", "data-table"), ":root { x: 1 }");
});

test("scopeCss scopes a non-global element selector and every selector in a comma list", () => {
  assert.equal(scopeCss("div, .row { x: 1 }", "data-table"), ".data-table div, .data-table .row { x: 1 }");
});

test("scopeCss keeps a group at-rule prelude but scopes the rules inside it", () => {
  assert.equal(scopeCss("@media screen { .row { x: 1 } }", "data-table"), "@media screen {.data-table .row { x: 1 }}");
});

test("scopeCss scopes the rules inside @supports and @container, like @media", () => {
  assert.equal(scopeCss("@supports (display: grid) { .row { x: 1 } }", "data-table"), "@supports (display: grid) {.data-table .row { x: 1 }}");
  assert.equal(scopeCss("@container (min-width: 1px) { .row { x: 1 } }", "data-table"), "@container (min-width: 1px) {.data-table .row { x: 1 }}");
});

test("scopeCss leaves a non-group at-rule body verbatim", () => {
  assert.equal(scopeCss("@font-face { font-family: x }", "data-table"), "@font-face { font-family: x }");
});

test("scopeCss joins scoped rules on newlines", () => {
  assert.equal(scopeCss(".a { x: 1 } .b { y: 2 }", "data-table"), ".data-table .a { x: 1 }\n.data-table .b { y: 2 }");
});

test("tokenContractViolations reports a clean organism as having no violations", () => {
  const manifest = { block: "button", tokens: { "--button-height": "Control height" } };
  assert.deepEqual(tokenContractViolations(manifest, "a { height: var(--button-height) }"), []);
});

test("tokenContractViolations catches non-namespaced, unused, and undeclared tokens, exempting shared tokens", () => {
  const manifest = {
    block: "data-table",
    tokens: { "--data-table-bg": "d", "--wrong": "d2", "--data-table-unused": "d3" },
  };
  const css = "a { color: var(--data-table-bg); margin: var(--ht-space-md); background: var(--data-table-extra) }";
  assert.deepEqual(tokenContractViolations(manifest, css), [
    "declared token --wrong is not namespaced under --data-table-",
    "declared token --data-table-unused is never referenced via var() in the CSS",
    "CSS references --data-table-extra but style.json does not declare it",
  ]);
});

test("mergeTokenContracts merges distinct component tokens into one contract", () => {
  const manifests = [
    { block: "button", tokens: { "--button-height": "h" } },
    { block: "data-table", tokens: { "--data-table-bg": "b" } },
  ];
  assert.deepEqual(mergeTokenContracts(manifests), { "--button-height": "h", "--data-table-bg": "b" });
});

test("mergeTokenContracts fails loudly, naming both owners, when two components declare the same token", () => {
  const manifests = [
    { block: "button", tokens: { "--shared-x": "a" } },
    { block: "switch", tokens: { "--shared-x": "b" } },
  ];
  assert.throws(() => mergeTokenContracts(manifests), /--shared-x is declared by both button and switch/);
});
