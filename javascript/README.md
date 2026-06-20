# Honest Framework — JavaScript reference implementation

This is the JavaScript track of the Honest Framework. The normative specifications live in
[`../specs/`](../specs/); the mature reference implementation is [`../python/`](../python/).

## Status

- **`honest-state/`** — implemented. The DATAOS client primitives (`collect` / `apply` /
  `observe`, the HTMX extension, cache-and-replay refresh recovery). These are JavaScript-only
  by spec (§6.1: the DOM is the only copy of user state), with a `node --test` suite.
- **`parse`, `type`, `check`, `test`, `persist`** — not yet built. The bootstrapping path below
  is how they come in.

## Bootstrapping (read the spec first)

The normative path is **[Bootstrapping a New Language Implementation](../specs/01-framework/honest-framework-spec.md#bootstrapping-a-new-language-implementation)**
in the Tier-1 spec. It is built **gate-first, in dependency order** — the verifier stands up
before the modules it certifies — not module-first-tested-after. What follows is only the
JavaScript-specific concretion of that path.

### Build order (the dependency DAG)

```
parse                       the shared parsing boundary — wraps tree-sitter; no framework deps
type                        the pure type system — no framework deps
check      → parse          the structural gate
test       → parse, type    the generative verifier
persist    → type
```

`parse` is the base, not `check`. JavaScript already has a tree-sitter grammar, so the boundary
is a thin wrapper over the tree-sitter JavaScript grammar through the host's tree-sitter
bindings — tree-sitter is the framework's sole AST mechanism, the same family that parses the
Python reference. Nothing else touches the parser directly.

### The seed-then-gate phases

1. **Seed `parse`** — hand-verify the wrapper against the parser-boundary laws (node-text
   round-trip, walk completeness and pre-order, 1-based line/col, error detection as a
   biconditional, determinism, a closed language vocabulary, correct text decoding). The
   `node --test` runner (already used by `honest-state/`) is the seed harness.
2. **Seed `check`** — write the structural rules, then run them on their own source until clean.
   Note the shortcut: honest-check's structural rules are tree-sitter *shapes*, so registering
   the JavaScript grammar in the boundary lets the same rule shapes gate `.js`/`.mjs`/`.cjs` —
   the structural stage is shared across languages, not reinvented per language.
3. **Seed `test`** — write the generators, then have them verify their own laws.
4. **Gate everything else** — every remaining module, and re-verification of the seeds, lands
   only by passing the structural gate and its conformance.

### Two conformance artefacts per module

- **The portable contract** — the same `suite.json` files the Python modules carry
  (`../python/honest-*/conformance/suite.json`) are language-agnostic input/output cases. The
  JavaScript modules must pass the *same* data. Do not fork or reformat them.
- **The generative proof** — a JavaScript harness (`laws_*.mjs`) that drives each module's
  declarations through the JS generators and asserts its laws across the generated space —
  predicates, functions, composed types, fake boundaries, malformed input: everything the JSON
  cannot express.

### Completeness is measured

The bar is **100% line and branch coverage, enforced as a gate** (a branch-coverage tool wired
to fail below 100%). An unhit line is dead code or an unspecified behaviour. Entry points are
covered by executing them, never by exclusion — no carve-outs.

## Invariants

- Match the same `../specs/` as the Python implementation.
- No classes (Honest Code); dict-lookup dispatch over `if/else` chains; DOM/I-O at the boundary.
- "HTML attributes over imperative JS" and DOM-as-state are non-negotiable.
- Plain ES modules; no bundler-required build (`<script type="module">` must load directly).
