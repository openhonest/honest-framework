// The brace-aware CSS rule splitter (honest-components §6.2, rules.js). Its whole reason to exist is that
// braces hide inside comments and strings, so the cases here drive a `}` and a `{` through a comment and
// through single- and double-quoted strings (where they must stay inert), a `/` inside a value (which must
// not start a comment), a `*}` inside a comment (which must not end it early), a nested @media block,
// adjacent rules, and a leading brace — every mode and depth transition the walk can make.
import { test } from "node:test";
import assert from "node:assert/strict";
import { splitRules } from "../src/index.js";

test("splitRules splits a plain rule into its prelude and body", () => {
  assert.deepEqual(splitRules("a { x: 1 }"), [{ prelude: "a ", body: " x: 1 " }]);
});

test("splitRules keeps a leading comment inside the following prelude and skips its braces", () => {
  assert.deepEqual(splitRules("/* c */ a { x: 1 }"), [{ prelude: "/* c */ a ", body: " x: 1 " }]);
});

test("splitRules does not treat a brace inside a comment as structural", () => {
  assert.deepEqual(splitRules("a { /* } */ x: 1 }"), [{ prelude: "a ", body: " /* } */ x: 1 " }]);
});

test("splitRules does not end a comment early at an asterisk that is not followed by a slash", () => {
  // The `* }` inside the comment must not close it: `*` alone is not `*/`, so the `}` stays protected.
  assert.deepEqual(splitRules("a { /* * } */ z }"), [{ prelude: "a ", body: " /* * } */ z " }]);
});

test("splitRules does not treat braces inside a single-quoted string as structural", () => {
  assert.deepEqual(splitRules("a { content: '}{' }"), [{ prelude: "a ", body: " content: '}{' " }]);
});

test("splitRules does not treat braces inside a double-quoted string as structural", () => {
  assert.deepEqual(splitRules('a { content: "}{" }'), [{ prelude: "a ", body: ' content: "}{" ' }]);
});

test("splitRules does not start a comment at a slash that is not followed by an asterisk", () => {
  // The `/` in `1/2` is a division-looking value, not a comment start, so both rules split normally.
  assert.deepEqual(splitRules("a { w: 1/2 } b { x: 1 }"), [
    { prelude: "a ", body: " w: 1/2 " },
    { prelude: " b ", body: " x: 1 " },
  ]);
});

test("splitRules keeps a nested block inside its parent body rather than splitting it out", () => {
  assert.deepEqual(splitRules("@media x { a { y: 1 } }"), [{ prelude: "@media x ", body: " a { y: 1 } " }]);
});

test("splitRules begins each rule's prelude right after the previous rule's closing brace", () => {
  assert.deepEqual(splitRules("a{x:1}b{y:2}"), [
    { prelude: "a", body: "x:1" },
    { prelude: "b", body: "y:2" },
  ]);
});

test("splitRules handles a rule whose prelude is empty", () => {
  assert.deepEqual(splitRules("{x}"), [{ prelude: "", body: "x" }]);
});

test("splitRules drops text that is not part of any rule", () => {
  assert.deepEqual(splitRules("a{x}/* t */"), [{ prelude: "a", body: "x" }]);
});

test("splitRules keeps an unterminated comment open, swallowing the rest of the file", () => {
  // `/*/` opens a comment that never closes (the third char is comment body, not a `*/`), so everything
  // after it is comment and no further rule is emitted. This pins the skip of the second char of `/*`.
  assert.deepEqual(splitRules("a { color: red } /*/ b { x: 1 }"), [{ prelude: "a ", body: " color: red " }]);
});

test("splitRules does not restart a comment at the slash it just consumed to close one", () => {
  // After `*/` closes a comment, the standalone `*` that follows must stay inert code; if the closing `/`
  // were re-examined it would pair with that `*` into a new `/*`. This pins the skip of the closing slash.
  assert.deepEqual(splitRules("a { x: 1 } /* c */* b { y: 2 }"), [
    { prelude: "a ", body: " x: 1 " },
    { prelude: " /* c */* b ", body: " y: 2 " },
  ]);
});
