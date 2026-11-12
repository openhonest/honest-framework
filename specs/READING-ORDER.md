# Reading Order and Document Key

**Date:** October 6, 2026 **Status:** Active **Scope:** every specification and prose document in this repository

The repository holds 17,671 lines of Markdown across 52 files, plus 2,745 lines of Gherkin in `specs/features/` and two machine-readable files, `specs/rules.json` and `specs/finite-testability-vectors.json`. The build order in the framework spec is the nearest thing to a front door, and it answers a different question.

This document answers three questions. Which documents are canonical. What each document assumes you have already read. Which order to read them in, for each of four reasons someone picks up the repository.

## The build order is not a reading order

The framework spec, "Bootstrapping a New Language Implementation," lines 333 to 448, gives a dependency order for building an implementation. It is correct for that purpose and wrong for reading.

`parse` is first to build and has a short architecture spec that carries none of the vocabulary. `design` is second to build and introduces the `.hd` declaration format, which almost nothing else can be understood without. `type` is third and carries the concepts every other module assumes: manifest, recognizer, vocabulary, slot, binding, link, chain, fault, and rejection. A reader who follows the build order starts with the thinnest module spec in the tree and reaches the vocabulary on the third stop.

Reading order runs the other way. Concepts first, then the gate that enforces them, then the modules that use them, then the research apparatus that measures them.

## Track 1: evaluating the claim (about 1,400 lines)

For a reader deciding whether the framework is worth more time. Four documents, in this order.

1. `README.md`, all 66 lines. The gate is the definition: code that passes `honest-check` is Honest Code, and there is no partial credit.
2. `specs/GLOSSARY.md`, 68 lines. Every coined word in one table. Read it before any spec, not as a lookup afterward. The specs do not re-define their terms.
3. `specs/01-framework/honest-framework-spec.md`, lines 9 to 70 and 226 to 331. The definition, the origin, apophasis, the comparison with Haskell and Elixir, and the verification model. Skip the rest of this document on a first pass.
4. `principles/poka-yoke.md`, 173 lines. Why each rule exists: a design decision earns its place by making a named category of bug impossible to write.

A reader who stops here has the argument and none of the machinery.

## Track 2: implementing the framework in a new language (about 8,100 lines)

The longest track, and the one the build order was written for. Read in this order, which is the build order with the two documents that explain the vocabulary moved to the front.

1. `specs/GLOSSARY.md`, 68 lines.
2. `specs/02-code-quality/honest-type-architecture.md`, all 1,786 lines, read in order. This is the concept core: `classify()`, composed types, Maybe, the manifest, state machines, the chain execution model, fault and rejection semantics, and the conformance suite. Sections 14 and 15 are one-paragraph pointers to honest-check and honest-test and take a minute each.
3. `specs/02-code-quality/honest-design-architecture.md`, 293 lines. The `.hd` format, the four-column model, the intermediate representation, and the reader. Every module below declares itself in `.hd`, so this precedes the rest. `methodology/declaration-review-cycle.md`, 277 lines, is the companion: how a `.hd` is brought into agreement with its code, stated as checks over the reader's output. Read it when you start authoring declarations, not before.
4. `specs/02-code-quality/honest-parse-architecture.md`, 39 lines. The one parser: one reader that touches tree-sitter, one orchestrator that places source by its path, the closed grammar set, and the pure tree helpers. Short, and it grounds every "source is parsed" claim below.
5. `specs/02-code-quality/honest-check-architecture.md`, all 1,737 lines. The canonical rule set, 52 rules in 12 families, with the algorithm for each. Section 9.4, adoption levels, is the part an adopter will ask about first.
6. `specs/02-code-quality/honest-test-architecture.md`, 1,080 lines. Generation, honesty tests, mutation adequacy, and coverage.
7. `specs/honest-conformance-suite.md`, 775 lines. The 45 laws an implementation is measured against, by module.
8. `specs/finite-testability.md`, 94 lines. The shared predicate that `honest-check` enforces as a gate and the Slop Audit measures as an instrument. Short, and it settles what "testable" means for both.
9. The remaining code-quality specs, in build order: `honest-errors` (237), `honest-gherkin` (385), `honest-observe` (1,653), `honest-rca` (165), `honest-persist` (1,306), `honest-auth` (301), `honest-state` (113), `honest-features` (583).
10. The application-production specs, in build order: `honest-page` (483), `honest-DOM` (377), `honest-format` (250), `honest-components` (489), `honest-alerts` (694), `honest-boot` (87). Read `honest-alerts` sections 1 and 2 before `honest-page` section 4, for the reason given under Known defects.

`honest-estimate` (194 lines) is not in this track. It is authoring tooling that reads the `.hd` intermediate representation, and nothing depends on it.

## Track 3: writing application code (about 900 lines)

For a programmer who has to work inside the discipline, not build it.

1. `specs/02-code-quality/honest-code-principles.md`, 65 lines, twenty practices. `python/honest-check/PRINCIPLES-COVERAGE.md` maps each one to the rule that enforces it, and names the two that no rule enforces yet.
2. `specs/GLOSSARY.md`, 68 lines.
3. `specs/02-code-quality/honest-check-architecture.md`, sections 4.2, 5, 7, and 9.4. The rules that fire on application code, their form in each language, how to suppress one honestly, and what an adoption level commits to.
4. `methodology/contract-testing.md`, 152 lines, and `methodology/root-cause-analysis.md`, 43 lines.
5. `articles/honest-type-magic-article.md`, 256 lines, for the declarative attribute surface, and `articles/honest-testing-article.md`, 218 lines, for why nobody writes the tests.

## Track 4: reviewing the research (about 1,100 lines)

For a reviewer, a board member, or anyone judging the empirical claims.

1. `specs/research-protocol.md`, 264 lines. The study design, the instrumentation, and the arm's-length team requirement.
2. `specs/finite-testability.md`, 94 lines, in particular section 5, the gate and meter asymmetry, and section 9, governance and independence.
3. `specs/honest-conformance-suite.md`, "Conformance Levels" and the appendix on laws not testable by property-based testing.
4. `specs/02-code-quality/honest-test-architecture.md`, section 9.6, mutation adequacy.
5. `SPEC-CONFORMANCE-AUDIT.md`, 148 lines. What is built against what is specified, module by module.
6. `INSTRUMENT_CONE_SYNTHESIS.md`, 87 lines, flagged in its own first line as a placeholder.

## Document key

One line per document. "Assumes" names what a reader needs first. "Canonical" means no other document overrides it.

### Root

| Document | Lines | What it decides | Assumes |
|---|---|---|---|
| `specs/READING-ORDER.md` | this file | Four reading tracks, the document key, and the editorial defects still open. | nothing |
| `README.md` | 66 | The gate is the definition of Honest Code. Repository map, hook setup, relationship to the Slop Audit. | nothing |
| `SPEC-CONFORMANCE-AUDIT.md` | 148 | Built against specified, per module, as of July 8, 2026. | the module specs |
| `PLAN-GENX-SUBSUMPTION.md` | 55 | Approved, partly executed. `honest-format` landed; the other genX spokes unstarted. | honest-format |
| `integration-test-challenge.md` | 150 | The public challenge. Opens at the M2 milestone, bounties contingent on grant funding. | the gate |
| `INSTRUMENT_CONE_SYNTHESIS.md` | 87 | Placeholder, says so in line 1. The epistemic argument, not a spec. | nothing |

### Principles and methodology

| Document | Lines | What it decides | Assumes |
|---|---|---|---|
| `specs/02-code-quality/honest-code-principles.md` | 65 | **Canonical and only.** Twenty practices at the level of daily decisions. | nothing |
| `principles/poka-yoke.md` | 173 | Why a rule earns its place: it eliminates a named bug category or it does not ship. | nothing |
| `methodology/contract-testing.md` | 152 | How to map a user journey to functions and write tests that mean something. | the vocabulary |
| `methodology/root-cause-analysis.md` | 43 | Apophasis applied to debugging: attest the negative under a stated evidence set. | the framework spec on apophasis |
| `methodology/declaration-review-cycle.md` | 277 | How a module's `.hd` is brought into agreement with its code, as a loop of propose, review, remediate, with the reviewer's checks stated as predicates over the reader's output. | honest-design |

### Framework tier

| Document | Lines | What it decides | Assumes |
|---|---|---|---|
| `specs/GLOSSARY.md` | 68 | **Canonical.** Every coined term, in plain words. A term absent here does not belong in a spec. | nothing |
| `specs/01-framework/honest-framework-spec.md` | 1,198 | **Canonical** for the vision, apophasis, the verification model, the build order, the architecture overview, the naming conventions, and the HTML attribute prefix registry. The `honest-py`, `honest-js`, and `honest-rails` sections are the only place those three layers are described. | the glossary |
| `specs/finite-testability.md` | 94 | **Canonical.** The predicate shared by the gate and the audit, its verdicts, and the governance separating them. | nothing |
| `specs/honest-conformance-suite.md` | 775 | **Canonical** for the 45 laws, by module, with property-based skeletons. | honest-type §1 to §11 |
| `specs/research-protocol.md` | 264 | The study design and the function-point mapping. | the conformance suite |
| `specs/01-framework/event-modules-spec.md` | 373 | `honest-publish`, `honest-queue`, `honest-itil`, and `honest-forecast`. Proposed, not in the build order. | honest-observe |
| `specs/01-framework/event-modules-possibilities.md` | 157 | Exploratory notes behind the above. | the above |
| `specs/features/*.feature` | 2,745 | Executable Gherkin for 14 modules. The behavioural contract in the form the engine runs. | the module's spec |

### Code-quality tier

| Document | Lines | What it decides | Assumes |
|---|---|---|---|
| `honest-type-architecture.md` | 1,786 | **Canonical** for `classify()`, composed types, Maybe, the manifest, state machines (§9), chains, and fault semantics. Read in order; nothing in it is superseded. | the glossary |
| `honest-design-architecture.md` | 293 | **Canonical** for `.hd`, the four-column model, the intermediate representation, and the validator. | honest-type §1 to §7 |
| `honest-parse-architecture.md` | 39 | **Canonical** for the one parser: one reader onto tree-sitter, one orchestrator that places source by path, the closed grammar set, and the pure tree helpers. | honest-design |
| `honest-check-architecture.md` | 1,737 | **Canonical** for all 52 rules, the three invocation surfaces, suppression policy, and adoption levels. | honest-type, honest-design |
| `honest-test-architecture.md` | 1,080 | **Canonical** for generation, honesty tests, mutation adequacy, and coverage. | honest-check, honest-gherkin |
| `honest-gherkin-architecture.md` | 385 | **Canonical** for the BDD engine. Built before `test`, which runs on it. | honest-type |
| `honest-errors-architecture.md` | 237 | **Canonical** for the report intermediate representation, normalization, behaviour policy, and the rate limiter. Normalizes a browser error object and a Python exception into one report. | honest-type |
| `honest-observe-architecture.md` | 1,653 | **Canonical** for the event envelope, projections, OpenTelemetry export, browser instrumentation, and threshold feedback. | honest-type, honest-errors |
| `honest-rca-architecture.md` | 165 | **Canonical** for the causal intermediate representation, the fixpoint traversal, and the attestation. | honest-observe, methodology/root-cause-analysis |
| `honest-persist-architecture.md` | 1,306 | **Canonical** for schema, query, pool, and migration. Section 10 is the forbidden list. | honest-type, honest-observe |
| `honest-auth-architecture.md` | 301 | **Canonical** for the `AuthProvider` contract and boundary actor resolution. Authorization is ordinary business logic, not this module. | honest-type |
| `honest-state-architecture.md` | 113 | **Canonical** for the six kinds of state and the single-mutator law. Defines no primitives of its own; the state machine is honest-type §9. | honest-type, honest-DOM |
| `honest-features-architecture.md` | 583 | **Canonical** for flags as a bounded vocabulary, the handler table, and the A/B middleware. | honest-type, honest-check, honest-test, honest-observe |
| `honest-estimate-architecture.md` | 194 | Size, cost, and duration from the `.hd` surface. Section 15 lists what must be locked before it is load-bearing. Not in the build order. | honest-design |

### Application-production tier

| Document | Lines | What it decides | Assumes |
|---|---|---|---|
| `honest-page-architecture.md` | 483 | **Canonical** for the six required surfaces, the bootstrap sequence, the token set, and the route map. | honest-type, honest-alerts §1 to §2 |
| `honest-DOM-architecture.md` | 377 | **Canonical** for DATAOS: `collect()`, `apply()`, `observe()`. | honest-state §1 |
| `honest-format-architecture.md` | 250 | **Canonical** for the `hf-*` attribute grammar, the format vocabulary, and the declared manifest HC-REF004 resolves against. | honest-DOM |
| `honest-components-architecture.md` | 489 | **Canonical** for atoms, molecules, organisms, and the CSS namespace contract. Its own orientation section comes first. | honest-page, honest-format |
| `honest-alerts-architecture.md` | 694 | **Canonical** for actors, the mailbox as projection, the routing table, and `send_and_wait()`. | honest-observe, honest-persist, honest-auth |
| `honest-boot-architecture.md` | 87 | **Canonical** for the client bootloader. Last in the build order, shortest document in the tier. | honest-DOM, honest-format, honest-components |

### Articles and implementation notes

| Document | Lines | What it is |
|---|---|---|
| `articles/honest-advantages.md` | 152 | What the framework does that popular frameworks do not. |
| `articles/honest-testing-article.md` | 218 | Why the test suite is generated rather than written. |
| `articles/honest-type-magic-article.md` | 256 | The unordered attribute token form. |
| `python/README.md` | 100 | Reference implementation layout and gate commands. |
| `python/GLOSSARY.md` | 109 | Python-specific terms. Read after `specs/GLOSSARY.md`, not instead of it. |
| `python/CONTRIBUTING.md` | 91 | The five gates a commit must pass. |
| `python/honest-check/README.md` | 102 | Checker usage. |
| `python/honest-check/COMPLIANCE-AUDIT.md` | 27 | The checker checked against itself. |
| `python/honest-check/PRINCIPLES-COVERAGE.md` | 33 | Which principles have a rule. |
| `javascript/README.md`, `ruby/README.md` | 54, 45 | Placeholders. |
| `python/tree-sitter-honest-hd/README.md`, `python/tree-sitter-honest-jinja/README.md` | 5, 5 | Stubs. |

## Known defects still open

Fifteen documentation defects were found by reading the tree and eleven were fixed in the same pass, so they are not listed here. What follows is what remains, each one either a judgment call that needs a person or work with a cost.

**Law counts disagree between the suite and the protocol.** `specs/honest-conformance-suite.md` defines 45 laws across 7 modules: Core 21, Full adds 16, Complete adds 8. `specs/research-protocol.md` says 50 laws across 12 modules, Core 20, Full 42, Complete 50. The function-point estimate in that document's appendix is built on the 50. One of the two numbers is the real one, and the research output depends on which. This needs a decision, not an edit.

**`SPEC-CONFORMANCE-AUDIT.md` contradicts itself, table against detail.** The summary table gives `honest-persist` as SPEC-COMPLETE; the detail section heading reads "SUBSET (SQLite/Turso substantial; Postgres non-functional)." The table gives `honest-DOM` as complete for its observable logic; the detail heading reads "SUBSET (~45% of Full)." The table gives `honest-features` 10 of 10 library functions; the detail heading says 9 of 9. `honest-design` and `honest-rca` have table rows and no detail section at all. Reconciling these means re-auditing those four modules, which is real work rather than a correction.

**The audit counts 36 checker rules and 15 modules.** The honest-check row reads "36 of 36 static rules," against 52 in the canonical summary and the 47 the adoption levels assign. The closing score reads "of 15 modules," against 19 in the build order. Each figure counts something narrower than the canonical set, and neither says what.

**Two rules belong to no adoption level.** HC-P018 and HC-REF005 are specified, are statically decidable, and appear in no level. honest-check §9.4 now says so rather than leaving the gap silent, but the rules still need placing.

**Two principles are stated and unenforced.** No Implicit Defaults (14) and Atomic Test-and-Set Over Check-Then-Act (19). Both are decidable from source, so both are candidates for a rule. `python/honest-check/PRINCIPLES-COVERAGE.md` now records this.

**`page` and `alerts` each assume the other.** The build order gives `page → type` and `alerts → errors, observe, persist, state, auth`, with no edge between them. But `honest-page-architecture.md` §2 requires three honest-alerts surfaces and §4 specifies the SSE wiring contract, while the framework spec says alerts mounts into page. Whichever is read first needs a forward reference. Reading `honest-alerts` §1 and §2 before `honest-page` §4 is the shorter detour.

**Six modules have no feature file.** `specs/features/` covers 14 modules. `design`, `page`, `DOM`, `format`, `components`, and `boot` have none.

**`principles/poka-yoke.md` references `AGENTS.md`, which is not in the tree.**

**`honest-estimate` is specified and absent from the build order.** The spec places it downstream of honest-design and calls it authoring tooling. Either the build order should name it or the spec should say it is deliberately outside the order.
