# Plan — subsume genX into the Honest Framework as rebranded Tier 3 modules

**Status:** approved; spec-first execution under way. honest-format spec drafted (`specs/03-application-production/honest-format-architecture.md`) and registered in the build order (DOM → format → components); `fmtx`/`smartx` are its reference of record. **Implementation started** at `javascript/honest-format/` — increment 1 (value coercion + hf-type conversion) passes all five JS gates. Next honest-format increments: `format.js`, `detect.js`, `manifest.js` (unblocks HC-REF004), `bind.js`. Remaining spokes (uix/dragx/loadx/accx → components, navx → page, bindx → DOM) unstarted.
**Source library:** `~/dev/genX` (MIT, ~20k LoC JS + TS bindings + CSS), a declarative HTML-attribute client runtime.
**Target:** the application-production tier (`specs/03-application-production/`) and its `javascript/` reference implementation.

## Why

genX is the concrete client runtime the Tier 3 specs describe abstractly: behaviour declared in HTML attributes, no imperative wiring. That is not incidental — it is the framework's own **declarative-over-imperative** poka-yoke: a declarative surface eliminates the entire category of "the control was authored but never wired to its handler" bugs (the same dead-reference family HC-REF guards statically). Folding genX in gives Tier 3 its implementation content and puts the whole framework behind one governance, one gate, one brand.

## Decisions taken

1. **Structure — distribute across Tier 3**, not one module. genX's spokes map onto the module boundaries the specs already draw (DOM / components / page), plus a formatting home. No new catch-all "honest-genx" module is invented.
2. **Method — spec-first rebuild, genX as reference.** Each spoke's behaviour is written into (or extended in) its Tier 3 spec first, then reimplemented to pass all five gates (honest-check clean, 100% line+branch, mutation-adequate, portable value oracle, feature bijection). genX's logic is reference material, not code to lift. This is the standing discipline: spec is source of truth, no corner-cutting, bring reused logic fully up to standard.
3. **Scope — everything comes in except the commercial pieces.** `tablex.*` and `proprietary/edge-compilation` stay out (table/tablix is the commercial track). Every other spoke — including `bindx` — is in.

## Spoke → module map

| genX spoke | ~LoC | Honest home | Notes |
|---|---|---|---|
| `genx-common`, `domx-bridge`, `bootloader` | ~1.5k | honest-DOM (runtime core) | The attribute scanner / MutationObserver bridge / loader. honest-DOM keeps its narrow DATAOS primitive contract (`collect/apply/observe/on/send/replay`); this is the engine that drives them from attributes. |
| `fmtx` + `smartx` | ~1.4k | **honest-format** (proposed new Tier 3 module) | Number/currency/date/filesize/percent formatting. Does not fit DOM (state), components (BEM UI), or page (composition). Home to the `hf-*` formatting vocabulary the framework spec already references; **directly supplies the HC-REF004 declared-vocabulary manifest.** |
| `uix` | ~2.7k | honest-components | Universal UI components. |
| `dragx`, `loadx`, `accx` | ~4.6k | honest-components (behaviours) | Drag-and-drop, loading states, accessibility enhancement — declarative behaviours attached to components. |
| `navx` | ~2.3k | honest-page | Declarative navigation. |
| `bindx` (+ react/vue/svelte/angular) | ~5.1k | honest-DOM (surface) + honest-components | See "bindx reconception" below. Framework bindings become interop wrappers, consistent with honest-DOM's existing `stateless` React wrapper. |
| `tablex` (+ css), `proprietary/` | ~2.9k | **excluded — commercial** | table/tablix and edge-compilation are the author-retained commercial track. Never fold into FOSS. |

## bindx reconception (the one non-mechanical port)

Keep the **declarative binding surface** (attributes that say "this element reflects this value"); that surface is the bug-eliminating win. Drop the **imperative Proxy reactive store** — a client-side state store contradicts DATAOS ("DOM as the authority on state; no client-side state stores"). The binding is re-expressed against honest-DOM: the DOM is the single source, `collect()`/`apply()` move values, `observe()` reacts. The React/Vue/Svelte/Angular adapters re-export the same surface into those frameworks exactly as `stateless` re-exports the honest-DOM primitives as React hooks. This is a spec question to settle in honest-DOM before implementing bindx, not a mechanical translation.

## Rebrand scheme (to finalise per module as its spec is written)

- Module names: genX's `*x` suffix → `honest-*` (`fmtx` → honest-format, `navx` → honest-page navigation, `uix` → honest-components, etc.).
- Attribute prefixes need unifying: the framework spec §116 already uses `hf-money`/`hf-percent`; genX uses `fx-format="currency"`. Pick one grammar during the honest-format spec (type-in-name vs type-in-value) and make the spec, the HC-REF004 examples, and the implementation agree. The HC-REF004 text I just wrote uses genX's `fx-format` form as a placeholder — it will be rebranded when honest-format's attribute grammar lands.
- No genX/`genx.software`/`*.software` product branding in FOSS copy (site-branding is a separate concern).

## Sequencing

Tier 3 is last in the bootstrap order (`… → page → DOM → components → alerts`), so this is downstream of the modules still being built. But one deliverable is worth pulling forward because it closes an already-open thread:

- **First: honest-format's declared vocabulary manifest.** It is the smallest spoke, its `hf-*` pattern is already in the framework spec, and it is the exact prerequisite HC-REF004 waits on (genX must declare its `fx-*`/`hf-*` vocabulary as data). Delivering it unblocks the fourth HC-REF kind and validates the whole subsumption method on the least-entangled spoke.
- Then honest-DOM core (scanner/bridge) + the bindx reconception, since components and page depend on it.
- Then honest-components (uix + dragx/loadx/accx) and honest-page (navx).

## Out of scope / guards

- `tablex`, `tablex.css`, `proprietary/` — commercial; excluded, never referenced from FOSS.
- No lift-and-shift: no genX file is copied into `javascript/` unrebuilt. genX stays a read-only reference.
- Each landed spoke must pass all five gates before it counts as done (gate-passing is not spec-completeness on its own).

## Open items to settle in-spec

- honest-format: is it a distinct Tier 3 module, or a leaf of honest-components? (Proposed: distinct module — formatting is orthogonal to UI structure.)
- The `hf-` vs `fx-` attribute grammar unification.
- bindx's DATAOS re-expression (honest-DOM spec extension).
