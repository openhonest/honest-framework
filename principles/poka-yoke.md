# Poka-Yoke as the Velocity Principle

**Purpose.** This document captures *why* Honest Code's measured developer velocity materially exceeds industry baselines, and *how* to preserve that advantage as the framework grows. It is a framework-design meta-principle, not a spec.

**Audience.** Contributors to the Honest Framework, anyone reviewing a feature or rule proposal, any AI agent generating code inside the framework. When you are deciding whether a new capability earns its complexity, start here.

---

## The thesis

Honest Code's advantage over class-based frameworks is not primarily a stylistic preference. It is a structural velocity multiplier. Every bug category that a framework makes **structurally unreachable** is effort a developer never has to spend defending against that category. Industry productivity baselines are measured against stacks that leave most of those categories reachable. Honest Code doesn't.

The direct implication: *any Honest Code developer's steady-state throughput should exceed industry baselines by a margin roughly proportional to the catalogue of bug categories the framework has eliminated.* This is a testable claim, not a marketing one.

---

## The three-multiplier stack

Measured throughput in Honest Code at this time (250+ FP/month sustained, via GitHub commit history) is a product of three stacking factors:

1. **AI-pair pacing.** The visible part. An AI agent with full spec in context produces working code faster than a solo developer working unaided. Industry recognises this factor; benchmarks of "AI-assisted productivity" exist.
2. **Depth of knowledge and guidance quality.** The invisible part. A developer who knows the architecture cold and can give the AI precise constraints gets 1st-draft-correct output where an uncertain developer gets 3rd-draft-correct-after-rework output. No productivity tool captures this; it shows up in the commit graph as "low rework, high first-pass approval rate."
3. **Framework guardrails (poka-yoke).** The structural part. The class of bugs that never reach the codebase because the framework refuses to represent them. *This is the factor the Capers Jones baseline cannot see,* because that baseline was measured on Java/J2EE/Spring, stacks where every guardrail on this list is absent.

The first two multipliers apply to any disciplined developer in any language. The third is Honest Code's alone and is the one that can be extended by design decisions going forward.

---

## Empirical anchor: the paradigm-comparison experiment

The three-multiplier thesis is not purely theoretical. **Paper B (Paradigm AI Compatibility)**, preregistered as part of the DBSYG four-paper research program (OSF DOI 10.17605/OSF.IO/DBSYG), is specifically designed to quantify the link between code shape and AI code-generation correctness. It is the empirical test of the AI-pair-pacing multiplier as a function of paradigm.

**Design:**

- 25 programming problems (`public/tests/01-tax-calculation` through `25-config-resolver`, plus `sanity-check`), each specified as Gherkin + pytest
- 5 paradigm variants per problem:
  - **P1** — pure functions, TypedDicts, dispatch-table polymorphism (Honest Code)
  - **P2** — frozen dataclasses (immutable but still object-oriented)
  - **P3** — classes without inheritance (encapsulation)
  - **P4** — inheritance-based (classical OO)
  - **P5** — mixins + ABC (maximum class-heaviness)
- 3 AI models tested per variant: Claude, Gemini, GPT-4
- Measurement: converged-on-first-attempt rate, final pass rate, attempts to convergence, per-scenario failing test count

**What the data shows so far (Task 01, tax calculation, representative):**

| Paradigm | Claude | Gemini | GPT-4 | Converged first-try |
|---|---|---|---|---|
| P1 pure functions | 1.00 | 0.91 | 0.67 | 1/3 |
| P2 frozen dataclasses | 0.97 | 0.00 | 0.82 | 0/3 |
| P3 classes no inheritance | 0.97 | 0.00 | 0.52 | 0/3 |
| P4 inheritance | 1.00 | 0.00 | 0.76 | 1/3 |
| P5 mixins + ABC | 0.97 | 0.85 | 0.03 | 0/3 |

Gemini collapses to 0% on P2, P3, P4 (three entire paradigm tiers it cannot handle for this problem). GPT-4 degrades to 3% on P5. Claude is robust across most tiers but still only converges first-try under P1 and P4.

**What this means for the velocity argument:**

The AI-pair-pacing multiplier is **not a constant** across paradigms. It is a function of code shape. An AI agent working in Honest Code generates correct code at a materially higher rate than the same agent working in class-heavy paradigms. Velocity gains attributed to "AI pair programming" on Java/Spring are therefore **lower-bound estimates** of what the same AI can achieve on Honest Code.

When experiment B concludes across all 25 tasks and all 5 paradigms and all 3 models, we will have a quantitative, reproducible measurement of the paradigm-to-correctness function — something no traditional productivity study could have produced, because traditional studies predate AI pair-programming.

**Connection to the poka-yoke principle:** every bug category the framework makes structurally unreachable is a category the AI no longer generates. Experiment B measures the cumulative effect of those eliminations on AI output quality. Each new guardrail added to the framework is, in principle, a new data point the AI-correctness experiment can measure.

---

## The Capers Jones baseline caveat

Capers Jones' industry-leading productivity measurements (10–20 FP/month average team, ~50 FP/month elite team) are overwhelmingly drawn from Java, J2EE, and Spring projects. Those stacks contain, structurally, every one of:

- Class hierarchies with inheritance (bugs: MRO ambiguity, fragile-base-class, diamond inheritance)
- Mutable-state encapsulation (bugs: hidden state, initialisation-order, stale `self` references)
- ORM identity maps (bugs: stale entity, cascade-delete, transaction boundary leaks)
- Framework dependency injection at runtime (bugs: circular injection, scope mismatch, lifecycle misorder)
- Synchronisation primitives (bugs: deadlock, livelock, priority inversion, race conditions)
- J2EE entity beans, Spring beans, component scans (bugs: ambiguous autowire, missing @Component)
- ApplicationContext, servlet containers (bugs: container-lifecycle leaks, static reference captures)
- ExceptionMapper / AOP cross-cutting concerns (bugs: exception swallowing, wrong-order advice)
- Manual thread management (bugs: unchecked concurrent modification, ThreadLocal leaks)

Every one of these is a bug category that Honest Code makes structurally unreachable by refusing to represent its enabling mechanism. A developer writing Honest Code spends zero effort defending against these categories, whereas the Capers Jones sample spent material effort on all of them.

Implication: if your measured Honest Code velocity is 250 FP/month and the Capers Jones elite is 15–50 FP/month, that's not evidence of a superhuman; it's evidence that the stack differential is doing what the thesis predicts.

---

## Poka-yoke as a first-class design metric

Going forward, every proposed framework feature, every new `honest-check` rule, every tooling addition is evaluated against one primary question:

> **Which category of bug does this make structurally impossible?**

If the answer is *"none — it's merely convenient,"* the proposal ranks below features that name a bug category they eliminate. This is the poka-yoke rule.

Corollaries:

- When a new HC rule is proposed, it must state the category of defect it removes. Rules that only lint style do not clear this bar unless they also remove a defect category.
- When a new tool or subsystem is proposed, it must state the category of defect its existence removes. Tools that merely accelerate work without removing a category earn lower priority than tools that do both.
- When an AI agent proposes a feature, it must name the category. This document is part of its context; the expectation is explicit.

---

## Current inventory — guardrails already embedded

Each row: the architectural decision and the bug category it makes unreachable.

| Guardrail / rule | Bug category eliminated |
|---|---|
| **No classes** (HC-P003) | Hidden state, inheritance diamonds, MRO ambiguity, ORM identity-map bugs |
| **Dict-lookup polymorphism** (HC-P001) | If/elif/else ordering bugs, silent fall-through, missing-case runtime errors |
| **Pure functions / I/O at boundary** (HC008, HC-P004) | Side-effect-at-a-distance, hidden clock/random reads, impure-helper contamination |
| **Flat composition over inheritance** | super() ambiguity, method override conflicts, deep-stack debugging |
| **DATAOS (DOM as authority on state)** | Client–server state-sync bugs, Redux/store drift, shadow-copy staleness |
| **SQL over application caches** | Cache invalidation bugs, read-your-own-writes violations |
| **Typed faults at the boundary** (HC-P013) | Exception swallowing, control-flow-via-raise, unchecked exception propagation |
| **Bounded vocabularies → exhaustive testing** | Unknown-input bugs, edge-case miss, sampled-testing blind spots |
| **Chain contracts** (HC001, HC002) | Interface-mismatch between components, silently-dropped fields |
| **Guarded mutations** (HC-P015 + honest-persist §7.5) | TOCTOU, lost-update, stale-read-based writes |
| **State invariants + K-step sequences** (honest-test §5.4, §5.6) | Illegal-state-transition, multi-step aggregate bugs, orphaning |
| **Adversarial neighbour testing** (honest-test §3.6) | Near-miss injection, Unicode confusable attacks, control-char bypass |
| **Actor-identity-in-guard** (honest-auth, commercial) | Session-revocation TOCTOU, stale-actor privilege escalation |
| **Orchestrator non-compose** (HC-OR001) | Dispatcher-of-dispatchers nesting, invisible wire-up, I/O accounting loss |
| **Function role declaration** (HC-R001) | Orphan code, coverage gaps, hidden entry points |
| **Non-determinism monitor watch list** (HC008 published list) | Clock / random / env-var / I/O leaks into pure functions |
| **Recognizer-reuse detection** (HC-P014) | Field-swap attacks, generic-type-collision across slots |
| **Serializable isolation in honest-persist** (§11 conformance) | Write skew, phantom reads, concurrent-write loss, inconsistent snapshots |

Every row: a category, gone. Not "detected early" — gone.

---

## Open frontiers

Features in the current specs where additional poka-yoke is available but not yet embedded. Each would remove another category.

1. **Vocabulary-binding consistency across modules.** HC-P014 covers within-module recognizer reuse; cross-module aliases can drift. A `use module.vocabulary` declaration plus honest-check verification would eliminate *vocabulary skew* — two modules silently disagreeing on a shared type's Set membership.

2. **Chain-level I/O budget.** A chain can quietly accumulate boundary links over time. An explicit per-chain I/O budget (declared `io_budget: { reads: N, writes: M, emits: K }`) plus enforcement at honest-check time eliminates *hidden fanout* — a chain silently growing to cost 10× its original I/O budget.

3. **Manifest-field provenance.** A manifest key written by link N and read by link N+3 could be overwritten by link N+2, intentionally or accidentally. Declared per-key provenance (which links may write, which read) plus honest-check enforcement eliminates *accidental overwrite* and makes intentional overwrites explicit.

4. **State machine progress-closure.** HC-SM04 catches fully-dead states. A reachable non-terminal state with no path to any terminal state is a *livelock trap* — reachable, not terminal, no way out. HC-SM07 would reject machines admitting such states. Eliminates progress-failure bugs in workflows.

5. **Non-trivial guard requirement.** `transaction([guarded_mutation(target=..., guard=True, update=...)])` is syntactically legal and structurally useless. HC-P018 would flag guards that are trivially unconditional (literal `True`, `EXISTS(target)` without further constraint). Eliminates "I wrote a guarded mutation but forgot to constrain it" bugs.

6. **Two-phase classify correctness at the DSL level.** honest-design's visual tool could enforce connector-type compatibility structurally at design time (already scoped). When realised, it eliminates *type-mismatch-in-composition* before a line of runtime code is written.

7. **Chain idempotency declaration.** Chains with boundary links could declare explicitly whether they are idempotent (safe to retry) or not. honest-check could then enforce that retry logic only wraps chains whose idempotency is declared true. Eliminates "retried a non-idempotent operation and double-charged" bugs.

Each item: one more category, gone.

---

## Rule for framework decisions going forward

When a decision is being made — a feature added, a spec clause written, a rule promulgated, a tool built, a line of code committed by an agent — run it through the poka-yoke filter:

- **Name the category.** Which class of bug does this remove structurally?
- **Verify unreachability.** Is the bug category literally impossible to represent after this change, or merely caught by testing / runtime / human review?
- **Rank by categories eliminated.** Given two proposals, the one that eliminates a category wins over the one that merely accelerates or automates.
- **Refuse if no category.** If a proposal can't name a category, it is either (a) low priority, or (b) needs to be reframed until it earns its complexity.

---

## Why this document exists at root

This is velocity-multiplier calibration that affects every estimate, every spec decision, every AI-agent prompt in the tree. It is cited by:

- `AGENTS.md` — so any agent entering the workspace sees the poka-yoke lens as part of its context
- Future spec change reviews — feature proposals must name their category
- Velocity estimates — Capers Jones numbers are not the right benchmark; the document explains why

Update it when new categories are eliminated or new frontiers become concrete.
