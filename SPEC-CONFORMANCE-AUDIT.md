# Spec-Conformance Audit — current tree

Date: 2026-07-08
Method: one read-only audit agent per module, each comparing the committed
implementation under `python/` (and `javascript/` for honest-DOM) against its
governing spec under `specs/`. Every load-bearing "MISSING" verdict below was
then re-verified by direct `grep`/read against the source, not taken on the
agent's word.

Supersedes the 2026-06-15 `c281f2d` snapshot (which predates the module rebuilds
and is no longer accurate — it recorded honest-type at ~2/60 requirements; it is
now 60/60). That snapshot triggered the spec-first rebuild; this one measures how
far the rebuild has come.

## Why this audit exists — the trust failure it corrects

I repeatedly reported modules as "complete." What I actually meant was
"passes the gate": honest-check clean + 100% line/branch coverage + value oracle
+ mutation adequacy + feature bijection. **That gate proves internal
self-consistency of the code that was written. It does not prove the code
implements the spec.** Two reasons, both verified:

1. **Coverage is circular against the spec.** 100% line+branch coverage is 100%
   of the lines that *exist*, not 100% of the behaviours the spec *requires*. A
   module that implements a third of its spec can be 100% covered.

2. **The feature bijection is circular against the spec.** The self-check pairs
   one gherkin scenario to one function point — it catches an orphan function or
   an orphan scenario. It does **not** check the feature file against the spec,
   and the feature files are authored *from the code*. honest-DOM's own feature
   file says so at `javascript/honest-dom/features/honest-dom.feature:2-4`: "One
   scenario per function point: **the named functions of the JavaScript reference
   implementation.**" A spec requirement that never became a function never
   became a scenario, so the bijection is blind to it.

3. **Even the function→gherkin half is not mechanically enforced right now.**
   honest-check correctly defers HC-P008/009/012 to honest-test (spec §4.3), but
   honest-test never implemented HC-P009 detection — it exists only in a
   docstring (`honest-test/src/honest_test/coverage_data.py:1`). So *nothing*
   currently fails a build when a roled function has no gherkin. The "one gherkin
   per function point" invariant I kept citing is maintained by hand, not by a
   check.

The durable fix is a third traceability edge — **spec-requirement →
feature-scenario**, enforced so a numbered spec requirement with no scenario
fails the way an orphan function does today. This audit is the manual stand-in
for that missing check, and its per-module requirement lists are the seed
registry that edge needs.

## Per-module verdict

Verdicts use three honest categories:

- **SPEC-COMPLETE** — every normative requirement implemented; remaining spec
  sections are explicitly other tools (honest-check/honest-test) by the spec's
  own words.
- **COMPLETE AT MANDATE** — the module's own mandate is fully implemented; the
  unmet "Full/Complete" conformance levels require host-framework / boundary /
  application code the spec *intentionally* does not ship in this package.
- **SUBSET** — the implementation is a genuine partial of its own spec. These are
  the modules I wrongly called "complete."

| Module | Category | Fraction (by requirement) | Worst verified gap |
|---|---|---|---|
| honest-type | **SPEC-COMPLETE** | 60/60 | none |
| honest-errors | **SPEC-COMPLETE** | 27/27 | none |
| honest-gherkin | **SPEC-COMPLETE** | 13/13 | none |
| honest-features | **COMPLETE AT MANDATE** | 10/10 lib functions; validate_vocabulary now full §2.1/§10.2 | Full/Complete need app-layer routes/CLI (spec §11 defers) |
| honest-state | **COMPLETE AT MANDATE** | 17/18 | law + taxonomy + §1.3 DOM decomposition complete; remaining: hub-suite test that the §3 rules fire, and the JS-side DOM-single-store rule |
| honest-auth | **COMPLETE AT MANDATE** | 13/13 fns; all 5 gates | contract-shape gaps resolved; §4.7 authentication-honesty verifier, §2.4 missing-credential rule, §5.3 dev provider + adopter templates added; remaining: §9.2 hub conformance app + `[honest-auth-provider]` metadata |
| honest-check | **SPEC-COMPLETE for its rule set; HC-REF Tier C partial** | 36/36 static rules; HC002 first-link live; HC-REF001 (route) + HC-REF002 (template include/extends) + HC-REF003 (template class→stylesheet) live | Tier A/B and the template-class half of Tier C are enforced; the JS-emitted-class extension (`classList` in `h*-` modules) and the attribute→config-key kind remain — see the HC-REF note below |
| honest-observe | **SPEC-COMPLETE** | auth attrs + grouped metrics done | none (proof_checked, persist metrics, install_otel_exporter, dev-mode are by-design elsewhere/boundary) |
| honest-test | **SPEC-COMPLETE** | §4.4 + §8.2 + §8.4 done | none (the runner, HC-P009, and §6/§7 are not-gaps — by design) |
| honest-parse | **SPEC-COMPLETE for its grammar set** | 9 grammars (6 source + HTML + Jinja + CSS) | complete; the Jinja grammar (own `tree-sitter-honest-jinja`, `eba702c`) and the official CSS grammar (`a6437a1`) were added for HC-REF Tiers B/C |
| honest-persist | **SPEC-COMPLETE** | Native matviews; full inspector round-trip (columns, PK, defaults, FKs, indexes, check constraints); reconstruction restores everything attached to a rebuilt table; create/alter/drop all tested on a real PostgreSQL, a real SQLite, and a real Turso | §6.6 matviews native on PostgreSQL / backfilled on SQLite-Turso; §9.1 inspectors round-trip a full combined schema with zero churn. A SQL-validity gate runs every generated construction — create, alter, drop — against a real PostgreSQL, a real SQLite, and a real Turso (real DB, no mocks — spec §8.6; Turso via pyturso, verified not-1:1-with-SQLite — its adapter handles tuple rows and the missing `foreign_key_check`); it caught a seven-bug cluster (inline-FK create/drop order, matview drop order, PK nullability, FK/index/check-constraint round-trip, reconstruction under a view), all fixed, plus reconstruction silently dropping check constraints and user triggers. Reconstruction now restores columns, check constraints, indexes, dependent plain views, matview refresh triggers, and user triggers. Mutation and the real DB are decoupled: integration probes run in the normal/coverage pass, the mutation loop stays pure. RETURNING/upsert remain by-design out-of-scope |
| honest-alerts | **SUBSET** | schema/pure 100%; runtime 0% | no expiry/escalation pollers, no channel handlers, no SSE, no threshold sends — schema+validator layer only |
| honest-DOM | **SUBSET** | Full + §5 primitives | vanilla domx at Full; §5 browser-observability primitives and request_id-in-DOM/HTMX-event dispatch built and gated; the real browser-binding wrapper (live htmx detail, durations, observer old-values for dom.changed, classify) awaits the browser conformance harness. §4 React hooks are a community adapter, out of scope for the reference impl (no React in the test closure). Conformance suite has 3 cases |

Score: of 13 modules, **7 spec-complete, 2 complete-at-mandate, 4 genuine subsets.**

Remediation is proceeding in the spec's bootstrap/dependency order
(`specs/01-framework/honest-framework-spec.md` §299): parse → check → test →
observe → **rca** → persist → auth → state → features → DOM → alerts. Completed:
**parse**, **honest-check**, **honest-test**, **observe** (2026-07-08),
**persist**, **auth**, **state** (2026-07-11), **features** (2026-07-12),
**rca** (2026-07-20). Every code-quality module in the build order is now built.
`honest-rca` (the causal-completeness solver — apophasis for debugging, composes
parse/check/observe, methodology in `methodology/root-cause-analysis.md`) is
spec-complete: the causal IR, evidence hashing, the four deterministic signal
detectors plus marked judgment edges, fixpoint traversal, the computed bound, and
`validate_attestation` — the poka-yoke that makes fake RCA unrepresentable — all
pass the five gates. Then the application-production tier, starting with **page**.

One cross-cutting exception rides forward with honest-check: the Tier-1 "every
reference resolves" principle is a rolling capability, not a sealed one. Tier A
(HC-REF001) is live. Tiers B/C are **not blocked** — like Tier A they are testable
against synthetic fixtures, so they need no real reference app. What they need is
(a) a spec written first (HC-REF002+ as first-class rules, not trailing prose), and
(b) a grammar addition to parse for each new reference kind: a template grammar to
extract `{% include %}`/`{% extends %}` targets (parse's HTML grammar does not see
Jinja), and a CSS grammar to read a stylesheet's definitions. The styling-reference kind must be grounded in the framework's real idiom, not
guessed: components use **real BEM CSS classes** owned per component, anchored by
`data-component` as the BEM block name (honest-components, BEM namespace contract),
sharing static `--ht-` custom-property tokens (honest-page §7); a genX `h*-`
attribute runtime lazy-loads behaviour modules (framework spec, the h*- attribute
skill registry); dynamic-theme regeneration from a `style.json` token contract is
out of FOSS scope.
So Tier C's styling rule is a honest-components BEM-contract check (does a class
resolve to a rule the component's CSS defines, with its prefix matching
`data-component`), which cannot be specced until honest-components is read and
built. These are future honest-check work,
tracked in the HC-REF note and `PLAN-STATIC-REFERENCE-CHECK.md`, not part of any
module reported complete.

(Tier 3 honest-components and honest-page have specs but are not yet built in
this tree, so they are outside this audit's scope; they were never reported
complete.)

---

## Per-module detail

### honest-type — SPEC-COMPLETE (60/60)
Reserved words (all three layers), Set∩Set overlap, composed types with
requires/captures and no-ambiguity, maybe/Nothing, the two-pass classify
algorithm (all phases), tickets/rejections/manifest/fault schemas, chains
(sync/async/compose), state machines, and the catch-all sampling guard
(`_check_catch_all`, deterministic corpus, >95% reject) are all present and
correct. honest-check and honest-test are separate specs by design.

### honest-errors — SPEC-COMPLETE (27/27)
Both normalizers produce one `ExceptionReport` shape; faults-as-data; no hidden
I/O (environment/timestamp/now all injected); four frozen vocabularies; dict
dispatch not ladders; pure throttle returning `(decision, new_state)`; boundary
conditions exact (`<` not `<=`, 3600s hour). No gaps.

### honest-gherkin — SPEC-COMPLETE (13/13)
IR TypedDicts, faults-as-data (no `raise` off the boundary), bounded
vocabularies, fold semantics with immutable context stopping at first non-ok,
no global registration, exception classification table, single I/O boundary in
`cli.py`. All four prototype divergences (§11) fixed.

### honest-features — COMPLETE AT MANDATE (9/9 library functions)
`validate_vocabulary`, `initial_state`, `feature_state`, `validate_toggle`,
`apply_toggle`, `build_signature`, `verify_signature` (constant-time compare,
replay window), `changed_event`, `evaluated_event` all present and pure. The
"missing" pieces — `load_secret`, the toggle route, the A/B middleware, the CLI
caller — are assigned to the application/boundary by spec §11, and HF001/HF002
are honest-check's. Legitimately deferred, but it means **Full/Complete
conformance is not met by this package alone**.

### honest-state — COMPLETE AT MANDATE (17/18)
Every normative statement in §1 is now a tested function: the single-mutator law
(`second_mutator_legitimate`), the nine-kind taxonomy with one mutator each
(`state_kinds`/`mutator_of`), and the §1.3 DOM decomposition
(`dom_region_kind` — a region is user state, server state, or a mutator-less
projection). §1.3 was previously prose-only; it is now gated like the rest.
The §3 enforcement rules exist in honest-check (HC-P004 subsumes the
boundary-write rule since a persist write is I/O outside a boundary; HC-P016;
HC-SM01–05). Remaining gaps are integration-facing, not honest-state's Python
surface: (1) the hub conformance suite (§5) that asserts each §3 rule **fires on
a planted violation** is not yet written — the module tests the law's truth-table,
not the linter's firing; (2) the **DOM-single-store rule** is JS-side and belongs
to the in-progress honest-DOM JS toolchain. Its own mandate ("define the law and
the taxonomy; primitives live in home modules") is met.

### honest-auth — COMPLETE AT MANDATE (resolved 2026-07-11; the ~39% audit is superseded)
The Python reference surface is complete and passes all five gates (10
conformance laws, 0 lint errors, 100% line+branch, 294/294 value cases,
13-function bijection, mutation-adequate). The AuthProvider TypedDict (five
fields), the pure value-registry
(`empty_registry`/`register_auth_provider`/`registered_provider`, immutable),
`authenticate()` boundary dispatch, and `fault_status()` mapping were already
present; this session closed the contract-shape gaps the old audit flagged and
added the missing verifier:
- **`test_token_generator` contract resolved.** The framework has no methods, so
  spec §2.4 was corrected to a plain callable `test_token_generator(class,
  context) → Token`; the impl matches. There is no `.generate()` to be missing.
- **The six token classes are enforced.** `authentication_honesty(provider,
  context)` (§4.7) drives all six (valid/revoked/expired/malformed/missing/
  forged) through the boundary and returns `authentication_dishonest` listing any
  class whose outcome breaks the contract; `resolve_actor_deterministic` checks a
  token resolves the same way twice under fixed state.
- **`"unauthenticated"` mapping is guaranteed by design, not a gap.**
  `fault_status` falls back to the framework defaults (`unauthenticated → 401`),
  so the effective mapping always maps `unauthenticated` even when a provider
  ships `fault_mapping: {}`. §2.5's "as long as unauthenticated remains" holds
  structurally.
- **§2.4 missing-credential rule added.** A `None`/empty credential is
  `unauthenticated` before the recognizer, not malformed.
- **A dev provider ships (§5.3).** `dev_auth_provider` — plaintext username/
  password, empty stored password = any-password wildcard — registered
  explicitly, never a default (§3.2). Four adopter provider templates
  (auth0/firebase/supabase/clerk) live in `honest-auth/examples/`, outside the
  gate, failing closed until wired.

Remaining, integration-facing (not the Python surface): the **§9.2 conformance
app** — the synthetic-boundary application (actor resolved at the boundary and
passed inward as data, an expected HTTP response per token class, a check that no
operation reads an actor from request input) — is not built; like the
honest-state hub suite it is a hub-repo artifact (`honest/honest-auth-
conformance/`), and its `[honest-auth-provider]` package-metadata declaration
(name/conformance/version) goes with it. Domain-mutation prevention, determinism,
and boundary placement remain correctly deferred to honest-check/honest-test/
host, per [[auth-is-boundary-validation]].

### honest-check — SPEC-COMPLETE (resolved 2026-07-08; the audit's own claims were partly wrong)
Reading the spec directly corrected three of this module's audit claims:
- **HC001 is spec-correct, not a stub.** Its pseudocode (spec §4.2, lines
  439-445) is exactly "every link in a chain carries `@link` metadata, else
  error" — which `check_hc001` does. The boundary-vocabulary derivation at line
  461 belongs to **HC002's first-link check**, not HC001.
- **The JS watch-lists were more complete than claimed.** The IO list and the
  `new`-constructor traps (WebSocket/XMLHttpRequest/EventSource/Date) were
  already present. The real gap was member-**read** impurity, now fixed
  (commit ce361a7): `_js_reads_impure` traps `process.env` / `location.*` /
  `document.cookie` / `navigator.*` reads and `Symbol()`.

36 of 36 statically-verifiable rules are implemented for Python; test-time rules
(HC-P008/009/012) are correctly deferred. Both former gaps are now closed:
- **HC002 first-link boundary-vocab derivation** (spec line 461): **DONE and
  live** (2026-07-08). The first link's `accepts` is checked against the
  vocabulary derived from the route map + templates (honest-page §5/§9). Built
  spec-first — Verification First, the gate preceding the code it governs
  (framework spec §297): HTML grammar in honest-parse (6de18bb); `templates.py`
  scanner (6a148fe); `boundary.py` derivation + check + `boundary_diagnostics`
  (fe396f6, 6081d06); CLI wiring — a `[check] templates` key drives a per-file
  boundary pass (28cc395). An app whose first link accepts a field no template
  targeting its route sends now exits 1 with HC002; an interpolated `hx-post`
  path fires the "unknowable boundary" violation.
- **HC011 catch-all**: resolved by reconciling the spec to the pure-static design
  (eac7ae7). honest-check does not execute application code, so it emits an `info`
  routing to the runtime checks that decide it; the catch-all bug category is
  still made structurally impossible — honest-type's `vocabulary()` rejects it at
  construction and honest-test rejects it under the generated suite. The spec's
  stale "CLI/LSP sandboxed evaluator" note is gone.
- Minor: `pyproject.toml` declares `conformance = "python"`, not a valid level.

**New capability — static-reference resolution (HC-REF).** The Tier-1
Verification Model now carries "Every reference resolves, or the gate stops"
(framework spec, committed `15778f6`): every identifier a rendered surface emits
must resolve to a definition — the dual of "the input boundary is closed." HC002
already runs *route → template*; the `HC-REF` family runs the reverse.
**Tier A is built and gated (2026-07-12, `706c5e9`):** HC-REF001 —
`check_references` resolves every resolvable template action against the
project-wide route union; `scan_template` now carries the template path and each
site its 1-based location, so the diagnostic names where the dead reference is
authored; the CLI aggregates routes across all checked files and runs the check
once. **Tier B is built and gated (2026-07-12, `763d5bb`):** HC-REF002 —
`template_includes` reads each template through honest-parse's own Jinja grammar
(`tree-sitter-honest-jinja`, `eba702c` — the HTML grammar reads `{% %}` as opaque
text) and surfaces each include/extends tag with its literal targets (one plain,
several conditional, none dynamic); `check_template_references` resolves every
literal target against the template search path (templates dir + sibling `atoms/`
/`molecules/` roots), skipping dynamic ones. **The template-class half of Tier C is
built and gated (2026-07-12, `4188b4b`):** HC-REF003 — `stylesheet_classes` reads
each component stylesheet through the official CSS grammar (`a6437a1`; a pseudo-class
is not mistaken for a class), `template_class_references` extracts each element's
static class tokens (a class value carrying interpolation is skipped whole, the
stated bound), and `check_class_references` resolves each against the union of
defined classes — BEM namespace ownership stays honest-components' mount-time
concern. All red-first with pure probes and CLI-level tests; boundary/templates/cli
mutation-adequate. What remains of Tier C: the **JS-emitted-class** extension
(classes a client `h*-` module adds via `classList`, statically knowable from the
module source) and the **attribute→config-key** kind (scoped in
`PLAN-STATIC-REFERENCE-CHECK.md`).

### honest-observe — SPEC-COMPLETE (resolved 2026-07-08; re-verified)
Event envelope, `emit()`, all framework event builders, projections + snapshots,
HLC ingest + identity binding + rejection log, threshold projections, and
dev-tool formatting are implemented. Re-verifying corrected the audit's claims:
- **OTel `hf.auth.*` attributes — DONE** (378202f): `_auth_attrs` maps the auth
  partition to `hf.auth.caller_id/data_owner_id/factors_presented`.
- **`hf.proof.checked` — NOT observe's.** honest-test fully builds and emits it
  (`proof.py` `emit_proofs`), exactly as `hf.persist.*` events are built in
  honest-persist — the owning module builds its events (framework_events.py's own
  comment says so). Not a gap.
- **`install_otel_exporter` — the boundary's** (§7.4 reconciled, def26a7): observe
  produces the pure `otel_signal` projection; the SDK export loop is boundary I/O
  (honest-py), reached through an injected exporter, exactly as `emit`. observe
  never imports the OTel SDK. Same principle as HC011.
- **4 persist metrics** deferred to honest-persist (their event payloads are
  persist's); **dev-mode** is a boundary/config concern (§9.5: "controlled by
  config, not code"). Both by-design, not observe gaps.

- **2 link metrics — DONE** (aa86766): `link.fault_rate` and
  `link.p99_duration_ns` are built by giving the metric model a general grouping
  capability — `custom_metric` takes a `group` function so a metric's value is one
  number per group (per link), and `evaluate_threshold` fires per group,
  returning one `{group, fired, value}` per link. Developer-configurable (group on
  the metric, condition on the projection), not hardcoded; §8b.5 defines it
  (1184aeb). Aggregate metrics unchanged.

### honest-test — SPEC-COMPLETE (resolved 2026-07-08; audit re-verified)
Strong: the generation engine (Set enumeration, Fibonacci numerics,
length-bounded, adversarial classes 1–4), the value oracle + step library,
purity/mutation/idempotency/chain-contract/auth-honesty checks, state-machine
test generation, the four coverage measures, and the full mutation-operator set.
Re-verifying against spec+code corrected several audit claims:
- **§4.4 boundary isolation — DONE** (db40f26): `io_monitor` +
  `verify_boundary_isolation` trap I/O in a non-boundary link, recording without
  performing it.
- **No runner/CLI — NOT a gap.** §11 is the *output format*; honest-test is a
  library applications wire into their own runner (the conformance harness is for
  meta-testing). The spec mandates no `honest-test` command.
- **HC-P009 — NOT honest-test's.** §8.3 says the diagnostic comes *from
  honest-check*; honest-test's role (writing `coverage.json` / proof events) is
  done. (Note: no static rule currently emits it; see the self-check hole above —
  but that is honest-check's edge to build, not honest-test's.)
- **§6/§7 — deferred by design.** They are Complete-level and use honest-test's
  machinery from honest-persist / honest-features, not honest-test core.

All three real gaps are closed:
- **§4.4 boundary isolation — DONE** (db40f26): `io_monitor` +
  `verify_boundary_isolation` trap I/O in a non-boundary link, recording without
  performing it.
- **§8.2 BDD step scaffolding generator — DONE** (d15d3ad): `scaffold_chain`
  generates a chain's gherkin registry (given classifies → when runs → then
  asserts), verified end-to-end against a real gherkin scenario.
- **§8.4 HTTP assertion step library — DONE** (1d99b7f): all 23 standard steps
  (`register_http_steps`) over a normalized response/request dict the app's test
  client provides, honest-test staying framework-agnostic and pure. Verified
  end-to-end; each assertion exercised on a match and a mismatch.

### honest-parse — SPEC-COMPLETE (7 grammars) — resolved 2026-07-08 (f793594, 6de18bb)
The parse boundary and node helpers (`node_text`, `line_col`, `walk`,
`first_error_node`, UTF-8, determinism) were already correct. The six source
languages honest-check/honest-test lint are present in `_LANGUAGES` — Python,
JavaScript, Ruby, PHP (via the tag-aware `language_php()` handle), Go, Elixir —
plus the **HTML/HTMX template grammar** the single parser must also read. That
seventh grammar corrects a premature "6/6 complete" claim: framework spec "The
input boundary is closed" names the parser's languages as "Python, the HTML/HTMX
templates, and JavaScript," so honest-parse without HTML could not see the
template attributes HC002 derives a boundary vocabulary from. Each grammar is one
row plus a wrapper; a data-driven `_law_grammars` table checks all non-Python
grammars uniformly. Gate: honest-check clean, 100% coverage, 33 conformance cases
+ 8 laws, mutation 71 caught / 0 undeclared, bijection 12 = 12.

### honest-persist — SUBSET (SQLite/Turso substantial; Postgres non-functional)
Present and solid: schema diff/validate/deps/ambiguity, apply with table
reconstruction + FK lifecycle + Turso sync-pause, the **full abstraction
backfill** (enum/range/array/map/hierarchy via `expand_schema`), CHECK
parse+compile+enforce, the pool (routing/lifecycle/events), connect-with-retry,
the durable write-queue + supervisor, transactions, cutover, Pydantic + Django
loaders, and the full instrumentation event set. Verified gaps:
- **No PostgreSQL inspector** — `_INSPECTORS = {"sqlite": …, "turso": …}` only;
  `migrate()` on Postgres gets `None`. **Postgres does not work end-to-end**,
  despite being a declared dialect.
- **No view/trigger/procedure DDL renderers** in `apply.py._RENDERERS` — `diff()`
  detects those changes but `apply()` cannot execute them (§5.7 half-built).
- No RETURNING; no materialized-view refresh; FK `on_delete`/`on_update` parsed
  but not emitted; live introspection reads only columns.
- Beyond-spec (would need spec additions to reach declaro parity): upsert,
  atomic increment, bulk insert, complex WHERE, the three ORM query styles.

### honest-alerts — SUBSET (schema/validator layer only; no runtime)
Complete and correct: all schemas and validators (actors, message, termination,
routing, escalation-rule), the mailbox projection and `is_terminated` dispatch,
the lifecycle state machine, the supervisor's pure routing + delivery-plan
construction, surface rendering, and the event catalog. Verified gaps — the
entire runtime:
- **Expiry/escalation pollers do not exist** — referenced only in a comment
  (`events.py:19`); `alert.expired` is never emitted, so messages cannot expire.
- **Escalation never fires** — the validator exists; nothing acts on
  `escalation_ttl`.
- **No channel handlers** (email/SMS/webhook/Slack/Teams); `execute_deliveries`
  calls an injected `runtime.deliver` that has no implementation.
- **No SSE stream** and **no reply endpoint wiring**, so `send_and_wait` cannot
  complete.
- No threshold-triggered sends.
Actual level reached: **Core schema/validation only** — not even Core behaviour,
because `alert.expired` cannot be emitted.

### honest-DOM — SUBSET (~45% of Full)
The seven core functions and the HTMX extension have correct *logic*. Verified
gaps:
- **Signature mismatch with no bridge.** Every function takes injected boundary
  params (`query`, `bus`, `deps`) instead of the spec's parameter-free
  signatures, and **the browser-binding wrapper that would reach
  `document`/`localStorage`/`fetch`/`MutationObserver`/`sendBeacon` does not
  exist.** Callers cannot use the exported API directly against a real browser.
- **§4 React hooks are a community adapter, not a reference-impl gap.** A React
  adapter carries React as a dependency, which would pull unverified third-party
  code into the framework's dependency-free test closure, so the Foundation does
  not ship or gate it (honest-DOM §1.1, §4).
- **§5 browser observability — primitives built, real binding pending.**
  `emitBrowserEvent`, the four event builders, `redact` (privacy mode),
  `readRequestId`, and the request_id-in-DOM + HTMX-event dispatch are built and
  gated. The real browser-binding wrapper (`sendBeacon` bound to live htmx
  events, durations, the observer's old-values for `dom.changed`, and classify)
  awaits the browser conformance harness.
- Portable conformance suite has 3 cases (shortcuts only) vs the ~30 the spec
  implies.

---

## What "complete" must mean from here

A module is **complete** only when every numbered spec requirement is
implemented *and* gated — not when the built subset passes the gate. Until the
spec→feature edge is mechanical, each module carries an explicit conformance
line naming which spec requirements are met, which are deferred-by-design (and to
where), and which are genuinely unbuilt. "Passes the gate" is reported as exactly
that, never as "complete."
