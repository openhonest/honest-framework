// The CSS namespace contract (honest-components §6): the pure core of the styling model. Three functions,
// each a text-in/value-out transform with no DOM and no state, so honest-check and the component runtime
// share the same code and a Python or Ruby port must behave identically.
//
//   - scopeCss (§6.2): rewrite an organism's CSS so every selector it owns is scoped under its BEM block,
//     making "an organism's styles leak onto the rest of the page" structurally impossible.
//   - tokenContractViolations (§6.5): the style.json <-> CSS token bijection, so a token declared but
//     never used, or used but never declared, is caught before the page runs.
//   - mergeTokenContracts (§6.4): collect every component's declared tokens into one contract, failing
//     loudly on a duplicate key so styling never depends on component load order.
//
// The §6.4 :root default-VALUE block is deliberately absent: §6.4 says the runtime "merges their declared
// default values" while §6.5 says "token values are absent by design" and components "never declare their
// own CSS custom property values", and the spec names no place those defaults live. The value merge waits
// on that spec reconciliation; the key-level poka-yoke (duplicate detection) does not depend on it.

import { splitRules } from "./rules.js";

// The conditional group at-rules whose bodies hold nested style rules. Their preludes are left untouched
// (prefixing `@media (...)` with a class is invalid CSS — this is what §6.2 means by "leave @media alone")
// but the rules inside are still the organism's selectors, so they are scoped; otherwise an author could
// escape scoping by wrapping a rule in @media. Declared as data, not a branch.
const GROUP_AT_RULES = new Set(["@media", "@supports", "@container"]);

// The selectors §6.2 leaves global: the page-level elements and the universal selector. A selector led by
// one of these is intentionally global and is never scoped. Data, not a branch.
const GLOBAL_LEADERS = new Set(["html", "body", "*", ":root"]);

// Scope one organism CSS file under its BEM block (§6.2). Every rule the organism owns has its selectors
// prefixed with `.<block> ` unless the selector is already namespaced or is an intentionally global
// element; group at-rules keep their prelude and have their inner rules scoped by recursion. Declaration
// bodies are copied verbatim, so custom-property declarations and var() references are never touched
// (§6.3). Pure: same CSS text and block, same output. Inter-rule whitespace is normalised.
export function scopeCss(cssText, block) {
  return splitRules(cssText)
    .map((rule) => {
      const prelude = rule.prelude.trim();
      if (prelude.startsWith("@")) {
        const atName = prelude.match(/^@[\w-]+/)[0];
        const body = GROUP_AT_RULES.has(atName) ? scopeCss(rule.body, block) : rule.body;
        return `${prelude} {${body}}`;
      }
      const selectors = prelude.split(",").map((raw) => {
        const selector = raw.trim();
        const leader = (selector.match(/^(\*|:root|[a-zA-Z][\w-]*)/) || [""])[0];
        if (selector.startsWith(`.${block}`) || GLOBAL_LEADERS.has(leader)) {
          return selector;
        }
        return `.${block} ${selector}`;
      });
      return `${selectors.join(", ")} {${rule.body}}`;
    })
    .join("\n");
}

// The style.json <-> CSS token bijection for one organism (§6.5). A violation is raised for a declared
// token that is not namespaced under `--<block>-`, a declared token never referenced via var() in the CSS,
// or a block-namespaced var() reference the manifest does not declare. References to shared tokens from
// other sources (honest-page's `--ht-` base tokens, §6.3/§6.4) are not block-namespaced and are left to
// their own owner, so they are exempt from this bijection. Pure: manifest and CSS text in, findings out.
export function tokenContractViolations(manifest, cssText) {
  const prefix = `--${manifest.block}-`;
  const used = new Set([...cssText.matchAll(/var\(\s*(--[\w-]+)/g)].map((match) => match[1]));
  const violations = [];
  for (const token of Object.keys(manifest.tokens)) {
    if (!token.startsWith(prefix)) {
      violations.push(`declared token ${token} is not namespaced under ${prefix}`);
    } else if (!used.has(token)) {
      violations.push(`declared token ${token} is never referenced via var() in the CSS`);
    }
  }
  for (const token of used) {
    if (token.startsWith(prefix) && !Object.hasOwn(manifest.tokens, token)) {
      violations.push(`CSS references ${token} but style.json does not declare it`);
    }
  }
  return violations;
}

// Merge every installed component's token contract into one key->description map (§6.4). Because every
// token is block-namespaced, two components declaring the same key is a namespace violation, not two
// values to reconcile: the merge fails loudly, naming both owners, rather than silently picking a winner
// whose effect would depend on load order. Pure over the manifest list; throws on a duplicate key.
export function mergeTokenContracts(manifests) {
  const merged = {};
  const owner = {};
  for (const manifest of manifests) {
    for (const token of Object.keys(manifest.tokens)) {
      if (Object.hasOwn(merged, token)) {
        throw new Error(`token ${token} is declared by both ${owner[token]} and ${manifest.block}; every token must be unique across components`);
      }
      merged[token] = manifest.tokens[token];
      owner[token] = manifest.block;
    }
  }
  return merged;
}
