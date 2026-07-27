// The brace-aware CSS rule splitter behind the namespace scan (honest-components §6.2). Splitting on `{`
// and `}` naively breaks on comments and on braces inside strings (`content: "}"`), which would let a rule
// escape scoping — the exact leak §6.2 exists to prevent — so the walk tracks whether it is inside a
// comment or a string and counts a brace only in code. Each top-level `{...}` becomes one rule with its
// prelude (the text before the brace: a selector list or an at-rule prelude) and its body verbatim; a
// nested block (a rule inside @media) stays inside its parent's body for the scan to recurse into.

// Split CSS text into its top-level rules (§6.2). Returns one {prelude, body} per top-level `{...}`, with
// both slices verbatim so comments and declarations survive untouched. Text outside any rule (a trailing
// comment, whitespace) is not a rule and is dropped. Pure: same CSS text, same rules.
export function splitRules(cssText) {
  const rules = [];
  let mode = "code";
  let depth = 0;
  let braceOpen = -1;
  let ruleStart = 0;
  for (let i = 0; i < cssText.length; i++) {
    const char = cssText[i];
    const next = cssText[i + 1];
    if (mode === "comment") {
      if (char === "*" && next === "/") {
        mode = "code";
        i++;
      }
    } else if (mode === "single") {
      if (char === "'") {
        mode = "code";
      }
    } else if (mode === "double") {
      if (char === '"') {
        mode = "code";
      }
    } else if (char === "/" && next === "*") {
      mode = "comment";
      i++;
    } else if (char === "'") {
      mode = "single";
    } else if (char === '"') {
      mode = "double";
    } else if (char === "{") {
      if (depth === 0) {
        braceOpen = i;
      }
      depth++;
    } else if (char === "}") {
      depth--;
      if (depth === 0) {
        rules.push({ prelude: cssText.slice(ruleStart, braceOpen), body: cssText.slice(braceOpen + 1, i) });
        ruleStart = i + 1;
      }
    }
  }
  return rules;
}
