# Scoping Plan — static-reference resolution in honest-check

**Status:** Tier A built and gated (2026-07-12, `706c5e9`). Tiers B and C remain, scoped below.
**Principle:** framework spec, Verification Model, *"Every reference resolves, or the gate stops"* (Tier 1, committed `15778f6`). Methodology source: `methodology/contract-testing.md`, "Static references are boundaries too."
**Goal:** enforce, at the structural gate, that every identifier a rendered surface *emits* resolves to a definition elsewhere — the dual of HC002's "the input boundary is closed."

---

## What honest-check already has (verified)

The reverse of what we need is already built, which means most of the machinery is in place:

- **honest-parse** reads the HTML/HTMX template grammar (`parse_html`, tree-sitter-html).
- **`declgraph.extract_routes`** produces the mounted route patterns (method + path) from a source file's `ROUTES`.
- **The template scanner** produces, per template, a list of **sites** — each an `hx-*` action with its `method`, `path`, targeted `fields`, and a `resolvable` flag — plus `manifest_keys`.
- **`boundary.py`** already matches template sites to route patterns with `_normalize_path` (collapsing `/items/{id}` against `/items/{{item.id}}`).

**The gap:** HC002 runs *route → template* — for each mounted route, it derives the boundary vocabulary from the sites targeting it and checks the first link's `accepts`. It never runs *template → route*. A site whose `(method, path)` matches **no** mounted route is simply never visited: there is no chain to hang a diagnostic on, so nothing fires. A button whose `hx-get` points at a route nobody mounted renders, passes every shape test, and does nothing — the dead link, unflagged.

---

## The reference kinds, tiered by how much new machinery each needs

| Tier | Reference | Resolves to | New machinery needed |
|---|---|---|---|
| **A** | `hx-get` / `hx-post` / `hx-*` action target | a mounted route pattern | **none** — reuse `extract_routes` + template `sites` + `_normalize_path` |
| **B** | `{% include %}` / `{% extends %}` | a template file that exists | extend the template scanner to capture include/extends targets; resolve against the scanned template set |
| **C** | `class="…"` / `id="…"` | a CSS rule the stylesheet defines | a **CSS grammar in honest-parse** (not present today) or a pragmatic selector extractor + stylesheet scan |
| **C** | attribute value (e.g. `onclick="openMenu('X')"`) | a key in a client-side config object | JS parse + config-object key resolution — ties to the in-progress JS toolchain |

Recommended order is **A → B → C**: A is the highest value (the literal dead link/button) at the lowest cost (no new grammar), and C is gated on machinery that is either absent (CSS) or still being built (JS).

---

## Tier A — the first move (detailed)

A new check: **every template action site resolves to a mounted route.** For each scanned site, assert its `(method, normalized path)` matches some route pattern across the scanned route map; if none matches, emit a dangling-reference diagnostic at the template location.

1. **Spec** — add the rule to `honest-check-architecture.md` (a new **HC-REF001**, "template action target resolves to a mounted route"), citing the Tier-1 principle it implements. Spec leads; the rule text names the bug category (dead link) and the resolution algorithm (site `(method, path)` ∈ route patterns).
2. **RED** — add honest-check test cases in the module's own conformance: a template whose `hx-get` targets a mounted route passes; one targeting an unmounted route fails with HC-REF001. Confirm red against current code.
3. **GREEN** — add `check_hc_ref001` in a new `references.py` (or alongside `boundary.py`, since it shares the scanned-sites/route inputs): pure over the already-parsed route map and scanned sites, reusing `_normalize_path`. Register it in `_ALL_CHECKS`. The template location comes from the site record; add site line/col to the scanner if not already carried.
4. **Wire** — the check needs the same `(routes across the project, scanned_templates)` inputs `boundary.py` already receives at the CLI seam; confirm the site records carry a source location for the diagnostic (extend the scanner minimally if not).
5. **Re-gate** — honest-check lint on itself, 100% coverage, value oracle, feature bijection (one scenario per new function), `mutate.py check:references.py` mutation-adequate.
6. **Commit** `spec:` for the rule, then `impl:` for the check (or one `impl:` if the spec rule is a one-liner addition — spec still lands first in the diff).

**Open decision for Tier A:** routes are declared per-file, but a template can target a route mounted in a *different* file. HC002 sidesteps this by checking per-file. Tier A needs the **union of all mounted routes across the project** to avoid false "dangling" positives for cross-file targets. Confirm the CLI already aggregates the route map project-wide (the template scan is already project-wide); if not, aggregating routes is a prerequisite and belongs in this tier.

---

## Dependencies and out of scope

- **Tier C (CSS) is blocked** on a CSS grammar in honest-parse — a honest-parse work item to file before it can start. Until then, a pragmatic class/selector extractor is possible but is not the single-parser-clean form the framework wants; note that trade-off rather than smuggling it in.
- **Tier C (config key)** rides on the JS toolchain already in progress; sequence it after the JS reference-resolution primitives land.
- **The elimination tier** — generating the agreeing artifacts from one declaration (the deeper remedy in the principle) — is a honest-DOM / honest-components / honest-page concern (single-source rendering), not a honest-check rule. honest-check is the *guard* that holds until a surface reaches single-source form. Out of scope here; note it as the eventual direction.

---

## Definition of done (Tier A)

- `honest-check-architecture.md` carries HC-REF001 citing the Tier-1 principle.
- A template action targeting an unmounted route is flagged at its location; one targeting a mounted route (including interpolated path params) is silent; proven by red-first honest-check conformance cases.
- The check is pure over already-parsed inputs, registered in `_ALL_CHECKS`, and passes all five gates on honest-check itself.
- The cross-file route-aggregation decision is resolved (project-wide route union, or documented as already aggregated).
- Tiers B and C are recorded here with their prerequisites (template-scanner extension; CSS grammar; JS config resolution) for a later pass.
