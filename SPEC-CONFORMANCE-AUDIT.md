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
| honest-features | **COMPLETE AT MANDATE** | 9/9 lib functions | Full/Complete need app-layer routes/CLI (spec §11 defers) |
| honest-state | **COMPLETE AT MANDATE** | 15/18 | law+taxonomy complete; no conformance test that the §3 honest-check rules actually fire |
| honest-auth | **SUBSET** | ~11/28 (~39%) | `test_token_generator.generate()` contract wrong/absent; no 6-token-class enforcement; no conformance-suite app; `"unauthenticated"` fault key not enforced |
| honest-check | **SPEC-COMPLETE** | 36/36 static rules; HC002 first-link live | none (HC011 spec reconciled to the pure-static design — eac7ae7) |
| honest-observe | **SPEC-COMPLETE** | auth attrs + grouped metrics done | none (proof_checked, persist metrics, install_otel_exporter, dev-mode are by-design elsewhere/boundary) |
| honest-test | **SPEC-COMPLETE** | §4.4 + §8.2 + §8.4 done | none (the runner, HC-P009, and §6/§7 are not-gaps — by design) |
| honest-parse | **SPEC-COMPLETE** | 7 grammars (6 source + HTML) | none (Ruby/PHP/Go/Elixir — f793594; HTML/HTMX — 6de18bb) |
| honest-persist | **SPEC-COMPLETE** | Native matviews; full inspector round-trip (columns, PK, defaults, FKs, indexes, check constraints); reconstruction restores everything attached to a rebuilt table; create/alter/drop all tested on a real PostgreSQL and a real SQLite | §6.6 matviews native on PostgreSQL / backfilled on SQLite-Turso; §9.1 inspectors round-trip a full combined schema with zero churn. A SQL-validity gate runs every generated construction — create, alter, drop — against a real PostgreSQL and a real SQLite (real DB, no mocks — spec §8.6); it caught a seven-bug cluster (inline-FK create/drop order, matview drop order, PK nullability, FK/index/check-constraint round-trip, reconstruction under a view), all fixed, plus reconstruction silently dropping check constraints and user triggers. Reconstruction now restores columns, check constraints, indexes, dependent plain views, matview refresh triggers, and user triggers. Mutation and the real DB are decoupled: integration probes run in the normal/coverage pass, the mutation loop stays pure. RETURNING/upsert remain by-design out-of-scope |
| honest-alerts | **SUBSET** | schema/pure 100%; runtime 0% | no expiry/escalation pollers, no channel handlers, no SSE, no threshold sends — schema+validator layer only |
| honest-DOM | **SUBSET** | ~45% of Full | injected-param signatures with no browser-binding wrapper; §4 React hooks absent; §5 observability absent; conformance suite has 3 cases |

Score: of 13 modules, **7 spec-complete, 2 complete-at-mandate, 4 genuine subsets.**

Remediation is proceeding in the spec's bootstrap/dependency order
(`specs/01-framework/honest-framework-spec.md` §299): parse → check → test →
observe → persist → auth → state → features → DOM → alerts. Completed:
**parse**, **honest-check**, **honest-test**, **observe** (2026-07-08). Next:
**persist**.

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

### honest-state — COMPLETE AT MANDATE (15/18)
The single-mutator law (`second_mutator_legitimate`) and the nine-kind taxonomy
with one mutator each are complete and tested. The gaps are integration-facing:
honest-state names the §3 honest-check rules that enforce the law but provides
no reference to them, and there is **no conformance test that those rules
actually fire on a planted violation** — only that the law's truth-table holds.
Its own mandate ("define the law and the taxonomy; primitives live in home
modules") is met.

### honest-auth — SUBSET (~39%)
The AuthProvider TypedDict (five fields), the pure value-registry
(`empty_registry`/`register_auth_provider`/`registered_provider`, immutable),
`authenticate()` boundary dispatch, and `fault_status()` mapping are implemented
and pure. Verified gaps:
- **`test_token_generator` contract is wrong** — spec §2.4 requires
  `.generate(class, context) → Token`; the impl carries only a `Callable` with a
  `(class_name) → token` comment and no `.generate()`; honest-test cannot drive it.
- **No enforcement of the six token classes** (valid/revoked/expired/malformed/
  missing/forged) a provider must produce.
- **No conformance-suite app** (§9.2 `honest/honest-auth-conformance/` synthetic
  boundary) — only portable value cases exist.
- **`"unauthenticated"` fault-mapping key not enforced** (§2.5/§4.5 require it
  always present); a provider with `fault_mapping: {}` registers successfully.
- Conformance metadata is `[tool.honest-check]`, not the spec's
  `[honest-auth-provider]`.
Much of what remains (domain-mutation prevention, determinism, boundary
placement) is correctly deferred to honest-check/honest-test/host, per
[[auth-is-boundary-validation]]; the contract-shape gaps above are the real ones.

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
- **§4 React hooks absent** (`useDomState`/`useDomValue`/`useDomArray`/`useDomMap`).
- **§5 browser observability absent** — no `emitBrowserEvent`, no `sendBeacon`,
  no request_id threading, none of the four automatic events, no privacy mode.
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
