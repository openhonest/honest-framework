# Honest Framework — Ruby reference implementation

This is the Ruby track of the Honest Framework, intended to ship as a Rails-friendly gem. The
normative specifications live in [`../specs/`](../specs/); the mature reference implementation is
[`../python/`](../python/).

## Status

Nothing built yet. Ruby is Phase 2 of the language roadmap, after the Python and JavaScript
reference implementations stabilise. The bootstrapping path below is how it comes in.

## Bootstrapping (read the spec first)

The normative path is **[Bootstrapping a New Language Implementation](../specs/01-framework/honest-framework-spec.md#bootstrapping-a-new-language-implementation)**
in the Tier-1 spec. It is built **gate-first, in dependency order** — the verifier stands up
before the modules it certifies — not module-first-tested-after. What follows is only the
Ruby-specific concretion of that path.

### Build order (the dependency DAG)

```
parse                       the shared parsing boundary — wraps tree-sitter; no framework deps
type                        the pure type system — no framework deps
check      → parse          the structural gate
test       → parse, type    the generative verifier
persist    → type
```

`parse` is the base, not `check`. Ruby already has a tree-sitter grammar, so the boundary is a
thin wrapper over the tree-sitter Ruby grammar through the host's tree-sitter bindings —
tree-sitter is the framework's sole AST mechanism, the same family that parses the Python
reference. Nothing else touches the parser directly.

### The seed-then-gate phases

1. **Seed `parse`** — hand-verify the wrapper against the parser-boundary laws (node-text
   round-trip, walk completeness and pre-order, 1-based line/col, error detection as a
   biconditional, determinism, a closed language vocabulary, correct text decoding), using the
   gem's chosen test framework as the seed harness.
2. **Seed `check`** — write the structural rules, then run them on their own source until clean.
   Note the shortcut: honest-check's structural rules are tree-sitter *shapes*, so registering
   the Ruby grammar in the boundary lets the same rule shapes gate `.rb` source — the structural
   stage is shared across languages, not reinvented per language.
3. **Seed `test`** — write the generators, then have them verify their own laws.
4. **Gate everything else** — every remaining module, and re-verification of the seeds, lands
   only by passing the structural gate and its conformance.

### Two conformance artefacts per module

- **The portable contract** — the same `suite.json` files the Python modules carry
  (`../python/honest-*/conformance/suite.json`) are language-agnostic input/output cases. The
  Ruby modules must pass the *same* data. Do not fork or reformat them.
- **The generative proof** — a Ruby harness (`laws_*` specs) that drives each module's
  declarations through the Ruby generators and asserts its laws across the generated space —
  predicates, procs, composed types, fake boundaries, malformed input: everything the JSON
  cannot express.

### Completeness is measured

The bar is **100% line and branch coverage, enforced as a gate** (a coverage tool configured to
fail below 100%). An unhit line is dead code or an unspecified behaviour. Entry points are
covered by executing them, never by exclusion — no carve-outs.

## Invariants

- Match the same `../specs/` as the Python implementation.
- Idiomatic Ruby is encouraged (modules, blocks, symbols) — provided **no** architectural
  primitive (recognizer, vocabulary, binding, manifest, link, chain) is implemented as instance
  state on a class. Data is data; behaviour is pure functions over it.
- Faults are data, not exceptions, except at the boundary; dict/hash-lookup dispatch over
  `case`/`if` chains; I/O at the boundary.
