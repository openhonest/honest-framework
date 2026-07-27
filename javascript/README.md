# Honest Framework — JavaScript reference implementation

This is the JavaScript track of the Honest Framework. The normative specifications live in
[`../specs/`](../specs/); the mature reference implementation is [`../python/`](../python/).

## Status

The client (application-production) tier is built and gated. The JavaScript-native bootstrapping seeds (`parse`/`type`/`check`/`test`) are not yet built, so the client modules are gated through the shared toolchain instead: honest-check's JavaScript rules run from `../python/honest-check`, coverage via `node --test`, and the function-point, feature, and mutation gates through the `javascript/*.py` harness against the Python workspace. Each module below passes the full `javascript/gate.sh` — honest-check clean, 100% line/branch/function coverage, portable conformance, one gherkin per function, and mutation adequacy.

- **`honest-dom/`** — built. The client DOM-as-state contract: `collect`/`apply`/`observe`, the HTMX extension, browser observability (instrumentation, beacon send, shortcuts), and the reload-recovery state cache. The DATAOS primitives — the DOM is the only copy of user state (honest-state §6.1) — live here. 29 function points, 3 portable conformance cases, and a Playwright real-browser suite (`e2e/`) that runs when Chromium is available.
- **`honest-boot/`** — built. The client bootloader: the full pipeline (scan → read → load → init → observe → emit) and every attribute notation, including the unordered Type Magic form. 15 function points and a Playwright `e2e/` suite; one open item (spec §10) is the exact path of the declared attribute-vocabulary file.
- **`honest-format/`** — built. Client-side value formatting: the format vocabulary, the formatter contract, smart auto-detection, and the DOM binding. 13 function points, 75 portable conformance cases.
- **`honest-components/`** — partially built. The client behaviour contract (§2.4 — the shared enhancement runtime with the switch and accordion) and the §6 CSS namespace contract (selector scoping, the `style.json` ↔ CSS token bijection, and the token-contract merge) are built and gated. Not yet built: organism packaging and discovery (§5.1), the mount-time application of the namespace scan, honest-type marshalling at the organism boundary (§7), and the multi-target organism structure (§8).
- **`honest-state/`** — not a JavaScript package. Its client half is DATAOS, implemented in `honest-dom` above.

The bootstrapping path below is how the JavaScript-native seeds (`parse`/`type`/`check`/`test`) arrive; until then the client tier rides the shared toolchain described above.

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

- **The portable contract** — a `conformance/suite.json` of language-agnostic input/output cases, run by `conformance/run.js`. For a module that also exists in Python (the bootstrapping seeds), it is the *same* data the Python module carries (`../python/honest-*/conformance/suite.json`) — do not fork or reformat it. The client-tier modules are JavaScript-only, so each carries its own native suite.
- **The adversarial proof** — for the client tier already built, the `node --test` unit suite (100% line/branch/function coverage), the feature-gate bijection (one gherkin per function), and `js_mutate` mutation adequacy together drive each module across predicates, boundaries, and malformed input. A dedicated generative harness in the style of Python's `laws_*.py` is the planned form for the bootstrapping seeds; it is not yet written.

### Completeness is measured

The bar is **100% line and branch coverage, enforced as a gate** (a branch-coverage tool wired
to fail below 100%). An unhit line is dead code or an unspecified behaviour. Entry points are
covered by executing them, never by exclusion — no carve-outs.

## Invariants

- Match the same `../specs/` as the Python implementation.
- No classes (Honest Code); dict-lookup dispatch over `if/else` chains; DOM/I-O at the boundary.
- "HTML attributes over imperative JS" and DOM-as-state are non-negotiable.
- Plain ES modules; no bundler-required build (`<script type="module">` must load directly).
