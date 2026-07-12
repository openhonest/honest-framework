# Spec Update Plan — honest-auth and honest-state

**Status:** COMPLETE (2026-07-11). Both specs were rewritten to a buildable state, the built honest-check/honest-test artifacts were reconciled to them, and **both modules are now implemented and pass all five gates** (see the closing section and `SPEC-CONFORMANCE-AUDIT.md`). This document is retained as the historical record of why the two specs were reconciled and what was decided; it drives no further work.

**Why this existed:** `auth` and `state` were the next two modules in the bootstrap build order (both dependency-unblocked), but neither could be implemented under the *spec → implementation → conformance* rule, because each spec was internally contradictory or unreconciled. This plan brought the two specs to a buildable state. It was **spec-only**: no module code was written until the specs settled and the named decisions were made.

`features` and `page` had no such debt and were buildable independent of this plan.

---

## The two debts (verified, not recalled)

### A. honest-auth depends on a guard DSL that honest-persist deleted

honest-auth's security model is: actor identity must be derived **atomically inside the mutation's guard (transaction)** via a `GuardExpressionTemplate`, which — per the auth spec — honest-persist compiles to a backend atomic operation:

- auth §1.2: *"the provider cannot derive the actor outside the atomic scope of the mutation's guard, because cross-scope derivation is vulnerable to … revocation … between derivation and commit."*
- auth §2.3 / §2.5: `derivation_expression: GuardExpressionTemplate`; *"consumed by honest-persist's **guard DSL (§7.5)** and compiled to a backend-specific atomic operation."*
- auth table (line 28): *"honest-persist | Exposes the provider's `derivation_expression` as a first-class clause inside the **guard DSL (§7.5 / §7.6 of honest-persist)**."*

honest-persist no longer has a guard DSL. Its single remaining "guard" reference is the **opposite** position (persist §, "Preconditions are ordinary code"): *"the developer writes that check as an ordinary early-return guard in the link before the write … The framework provides **no special check-and-write primitive** and does not promise to make overlapping transactions safe."*

So auth's atomic-guard mechanism is homeless: the host it names (persist §7.5/§7.6) was removed, and persist's current stance directly contradicts the "compiled atomic operation" auth assumes. honest-check rules **HC-A001/HC-A002** (built, mutation-adequate) and the auth conformance suite already encode the `derivation_expression`/guard concept, so the concept cannot simply be deleted — it must be re-homed.

### B. honest-state §1 is re-authored; §2–§7 are stale draft, with ownership that belongs elsewhere

honest-state is **v0.2 (Draft)**, status line: *"§1 re-authored as the foundation (taxonomy + single-mutator law); §2 onward is prior-draft mechanical detail under reconciliation."* §1 is sound: *there is no "the state"* (a taxonomy of kinds, each with one store and one mutator) and the **single-mutator law**. §2–§7 predate that foundation and, worse, describe mechanics that belong to **other modules**:

- **§2 User State / DATAOS** (`collect`/`apply`/`observe`, the State Manifest, HTMX integration). The build order assigns DATAOS to **honest-DOM** ("DOM-as-state (DATAOS) primitives"). This is honest-DOM's territory, duplicated in honest-state.
- **§3 Domain State / Pure-Function State Machines** (`state_machine`, `transition()`, data structures, history, terminal states). honest-type **already implements** `state_machine` (`honest_type/state_machine.py`, built and mutation-adequate). honest-state §3 re-specifies a mechanism that exists in honest-type.

So honest-state today claims ownership of DATAOS (→ DOM) and state-machine mechanics (→ type) on top of the genuinely-its-own §1 law. Building it as written would duplicate two other modules.

---

## Track A — honest-auth: re-home the atomic guard

### A0. DECIDED — authentication is a boundary concern

Identity is validated **at the boundary** (the FastAPI middleware, or the equivalent in another stack): the user is verified once at the edge, turned into a plain validated `actor` value, and passed inward as data. The pure business logic never re-checks; it receives the actor like any other input. This is the framework's own *I/O-at-the-boundary* rule applied to authentication — reading a token / hitting a session store is I/O, so it lives at the boundary, not in the middle.

The boundary→commit **gap is accepted**: identity is "good for this request," not re-verified at the instant of the write (nearly all web auth works this way). A stricter verify-at-write mechanism is **deliberately out of scope for this FOSS spec — do not describe it here.** If one operation needs a stricter per-write check, that is ordinary code (a plain early-return) inside that operation, not a framework feature.

Consequences for the rewrite:

- **Delete the atomic-guard machinery** entirely: `GuardExpressionTemplate`, "derive inside the transaction," and every reference to honest-persist's removed guard DSL (§7.5/§7.6).
- **Auth's surface becomes** validate-at-boundary → produce a validated `actor` value → pass it in. `AuthProvider` shrinks to what a boundary validator needs (recognize/validate a token, map failures to HTTP statuses); the in-transaction derivation clauses go.
- **Revisit honest-check HC-A001/HC-A002.** Their current wording ("an authorizing link references the identity derivation inside its guard") no longer fits a boundary model. Their boundary-model replacement (e.g. a mutating route must take its actor from the boundary validator, not from request input) is decided as part of the rewrite. Both rules are built and mutation-adequate, so the spec change drives a follow-up rule change.

### A1. Steps (after A0 is decided)

1. **Audit** every `GuardExpressionTemplate` / guard / atomicity claim in auth (16 refs, mapped) and the auth conformance suite, and the HC-A001/A002 wording in honest-check's spec.
2. **Rewrite** auth §1.2 (the atomicity rationale), §2.3 (`actor_recognizer`→guard handoff), §2.5 (`derivation_expression`/`GuardExpressionTemplate`), §4 (public contract: atomic-derivation clauses), §5 (example registrations) to the chosen model.
3. **Remove the persist references** (auth line 28 and §2.5's "guard DSL §7.5/§7.6"); replace with the chosen mechanism's home.
4. **Reconcile honest-persist** if the model needs anything from it (model 1/3: confirm persist's "preconditions are ordinary code" already suffices and add a one-line pointer; model 2: nothing in persist).
5. **Reconcile honest-test** §4.5 (determinism monitor) and the auth token-class table (these reference the guard's determinism) to the chosen model.
6. **Reconcile the conformance suite** (`honest-auth/conformance/suite.json` once the module is built; for now the spec's §9 suite description) so its cases match the new model.
7. **Patent boundary (§6).** auth has a "Relationship to Patent-Protected Implementations" section. Keep the spec at the **contract** level (what a provider must satisfy), never the patented mechanism. Per the track CLAUDE.md, do not move out-of-scope implementation detail into the FOSS spec.
8. **Verify alignment with what is already built:** honest-check HC-A001/HC-A002 and any auth references in honest-test are implemented and mutation-adequate. The rewritten spec must not contradict them; where it does, decide whether the spec or those rules move (spec leads, then the rules follow — but those rules currently match the *static* reading, which models 1/3 preserve).

---

## Track B — honest-state: reduce to its own law; push mechanics to their homes

### B0. DECIDED — honest-state is the law; mechanics live in their home modules (and it stays thin)

honest-state shrinks to its own unique job: **state the law and enforce it.** It re-describes no mechanism that has a home elsewhere; it names that home. Thin is the expected, correct outcome.

- **The law (kept).** There is no "the state": a taxonomy of state *kinds*, each with one store and exactly one mutator (a second mutator of a store is allowed only when it is honest and disjoint — never touches state another mutator owns).
- **The taxonomy names each kind's home and single mutator, and points there:**
  - **user / on-screen state → DATAOS** (DOM-as-state), in honest-DOM. The user is the single mutator; the screen is the store. **DATAOS is canonical and normative for every language and framework** — not a Python/HTMX detail.
  - **server-push state →** honest-alerts (the alert source is the single mutator).
  - **session / login state →** a shared store visible to all instances, with one authoritative writer.
  - **domain state →** the database (honest-persist) holds the value; a **honest-type state machine** owns its transitions, with `transition()` as the single mutator. **The type module's state machine is canonical and normative for every language and framework.**
- **The enforcement (kept).** The honest-check rules and honest-test integration that make every declared piece of state obey one-mutator — tying together HC-P016 (closures), the HC-P004 module-read clause, the boundary-write rule, and DOM-as-single-store. This is the part with no other home and the real reason honest-state is a module.
- **DATAOS detail moves to honest-DOM; state-machine mechanics are referenced from honest-type (already built), not re-specified.**

### B1. Steps (after B0 is decided)

1. **Audit** §2–§7 section by section against §1; tag each section **keep** (it's the law / cross-kind enforcement), **move-to-DOM** (DATAOS mechanics), or **move-to-type / reference** (state-machine mechanics).
2. **Rewrite honest-state** to §1 + the kept enforcement sections, with §2/§3 reduced to "this kind lives in module X; see that spec" pointers.
3. **Move** the DATAOS mechanical detail into honest-DOM's spec (or confirm honest-DOM already covers it and delete the duplication).
4. **Replace** §3's state-machine mechanics with a reference to honest-type's `state_machine` (and confirm honest-type's spec/impl already covers history/terminal/parallel/guards; file gaps as honest-type spec items if not).
5. **Reconcile** honest-state's honest-check integration (§4) and honest-test integration (§5) to enforce the single-mutator law across kinds — this is the part with no other home and is the real reason honest-state exists as a module.
6. **Reconcile the conformance suite** to the reduced surface; bump version/status out of Draft.

---

## Sequencing and dependencies

```
A (auth spec)   ── independent; unblocks alerts (needs auth)
B (state spec)  ── independent; unblocks DOM and alerts (both need state)
                   B touches honest-DOM and honest-type specs (ownership moves)
```

- **A and B are independent** and can proceed in either order or in parallel.
- **Neither blocks `features` or `page`** — those are buildable now and need no spec work.
- Each track ends at a **buildable spec**, not at code. Implementation (auth, state) follows under the normal four-gate bootstrap (shape, conformance, coverage, mutation adequacy), after the A0/B0 decisions are made and the rewrites land.
- **Spec changes propagate** per the stability rule: a Tier-2 change that touches honest-check rule wording (HC-A001/A002), honest-test (§4.5, token classes), honest-DOM, or honest-type must update those specs in the same pass, and the cross-tier conformance suite where affected.

## Status: specs rewritten, both modules built and gated

Both specs are rewritten and the spec layer is internally consistent:

- **honest-auth** — boundary-validation model (`AuthProvider` = name + `actor_recognizer` + `resolve_actor` + `test_token_generator` + `fault_mapping`); guard machinery and persist guard-DSL references deleted.
- **honest-state** — 700 → 113 lines; the single-mutator law, the taxonomy with pointers, and the cross-kind honest-check enforcement. DATAOS mechanics confirmed already owned by honest-DOM; state-machine mechanics already owned by honest-type — referenced, not duplicated.
- **honest-check** — HC-A001/HC-A002 reworded to the boundary model (actor must come from the boundary, not request input).
- **honest-test** — §4.7 reworded to probe `resolve_actor` over six authentication classes; authorization-for-target is ordinary link logic.

### Follow-up implementation changes — DONE

Both built artifacts were reconciled to the boundary-auth spec (each still mutation-adequate after the change):

- **honest-check HC-A001/HC-A002** (`8321067`) — HC-A002 now flags an authorizing link that does not use the boundary-resolved `actor`; the derivation-signature machinery (`registered_provider_signature`, `_derivation_signature`) was replaced by `is_provider_registered`. Concrete mechanism introduced and recorded in the auth + honest-check specs: the framework passes the resolved actor inward as the reserved name `actor`, and the link must reference it. honest-check at 0 undeclared (3879/189), 100% coverage, Honest.
- **honest-test `authhonesty.py`** (`db6528b`) — `test_auth_honesty(provider)` probes `resolve_actor` over six authentication classes (`valid` + revoked/expired/malformed/missing/forged), with a malformed token rejected by the `actor_recognizer`; per-provider, not per-link. Feature scenarios + suite.json value cases updated. honest-test at 0 undeclared (1905/85), 100% coverage, Honest.

### Modules built — DONE (2026-07-11)

Both modules were then implemented from the reconciled specs under the five-gate bootstrap (honest-check lint, 100% line+branch coverage, portable value oracle, feature bijection, mutation adequacy):

- **honest-auth** — the boundary-validation surface: `AuthProvider` contract, the pure value-registry, `authenticate()` dispatch, `fault_status()`, the §4.7 `authentication_honesty` / `resolve_actor_deterministic` verifier, the §2.4 missing-credential rule, a §5.3 `dev_auth_provider` (plaintext, empty-password wildcard, never a default), and four adopter provider templates (auth0/firebase/supabase/clerk) under `examples/`, outside the gate. All five gates green. Remaining, integration-facing: the §9.2 hub conformance app.
- **honest-state** — the single-mutator law (`second_mutator_legitimate`), the nine-kind taxonomy (`state_kinds`/`mutator_of`), and the §1.3 DOM decomposition (`dom_region_kind`). All five gates green. Remaining, integration-facing: the hub-suite test that the §3 honest-check rules fire, and the JS-side DOM-single-store rule.

The audit row for each is `COMPLETE AT MANDATE` in `SPEC-CONFORMANCE-AUDIT.md`.

## Definition of done (per track)

- No internal contradiction: every cross-reference resolves to a section that exists and agrees.
- No duplicated ownership: each mechanism is specified in exactly one module; others reference it.
- The built artifacts that already encode the concept (honest-check HC-A001/A002; honest-type `state_machine`) either match the spec or are listed as follow-up implementation changes.
- The spec states the **present design only** — no version/Draft/status lines, no "removed / previously / re-authored / under reconciliation" notes. It reads as if the design were always this way. (The change history lives here in the plan and in commit messages, never in the spec.)
