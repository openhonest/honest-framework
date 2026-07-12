# The Honest Framework Integration-Test Challenge

> **STATUS: Specification published for public review.** The Challenge opens when `honest-test`, `honest-check`, the reference todo application, and the runner image ship (M2 milestone). Cash bounty payouts activate concurrently with infrastructure launch and are contingent on grant funding being awarded. Until both gates land, the specification is open for community scrutiny and pre-launch attack design; attribution remains the operative incentive.

> *Dishonest code is mathematically UNTESTABLE.*
> *Honest Code is so easy to test YOU DO NOT WRITE TESTS YOURSELF.*
> *If we can't auto-generate tests from your code, your code is dishonest.*
> *Integration tests are the story we tell each other to make peace with the fact that our code is dishonest.*

---

## Claim being tested

The Honest Framework provides a pre-commit pipeline (`honest-check` + `honest-test`) that makes integration tests unnecessary. The pipeline collapses to a single principle:

1. **`honest-check`** asks: *can I auto-generate the complete test suite from this code's declarations?* If no → the code is dishonest → reject.
2. **`honest-test`** runs the auto-generated suite. If any test fails → the code is buggy → reject.

The developer writes no tests. The vocabulary, link, recognizer, state machine, and BDD-feature declarations are the test specification. Auto-generation reaches every function with a declared role and every function reachable from one. Coverage is structural, not audited.

Claim: integration tests are unnecessary because honest code, by construction, has a complete auto-generated test suite.

The challenge exists to falsify or confirm this claim publicly.

## The challenge

A public repository contains a moderately complex multi-user todo application built entirely with the Honest Framework:

- User registration and session management
- Task CRUD
- Sharing with three permission levels (read-only, read-write, owner)
- Ownership transfer
- Task search

The application passes `honest-check` (auto-generation succeeds) and `honest-test` (auto-generated suite passes) in under 60 seconds in CI. No hand-written tests exist. The auto-generation output is published on every commit.

Any member of the public may submit a pull request that satisfies **all four** conditions:

1. Modifies only implementation code (see scope rules).
2. **`honest-check` passes** — the code remains honest; auto-generation of the test suite still succeeds.
3. **The auto-generated test suite (`honest-test`) and the BDD feature suite both pass.**
4. **Contains a runtime bug that an integration test can catch** — a test that runs the application end-to-end against a real HTTP stack and a real database would have caught it with high probability.

A submission that satisfies all four wins.

## Scope rules

**Modifiable by the challenger:**

- Implementation code inside `@link`-annotated functions
- Template files
- Internal helpers

**Not modifiable:**

- Vocabulary declarations
- Binding tables
- `@link` declarations (signature, role, boundary flag, authorization declaration)
- State machine declarations
- Invariant declarations
- BDD `.feature` files
- Configuration

A challenger whose argument is "the spec itself is incomplete" — vocabularies or invariants were wrong, so the test suite structurally cannot catch the bug — may submit that argument as a separate, higher-value finding. It identifies a gap in the framework, not in the test suite.

**In-scope bug categories** (matching the framework's public claims, see below):

- Logic bugs inside chain links that produce wrong output
- Serialization or rendering bugs
- Missing error handling at boundaries
- State transitions that violate declared invariants
- Guard weakening that permits previously-forbidden mutations
- Chain composition bugs that corrupt data between links
- Routing or fault-mapping bugs
- Multi-step aggregate behaviors that violate invariants

**Out of scope:**

- Security attacks against the running system — the challenge is about test completeness, not penetration testing
- Performance bugs — slow code with correct output does not count
- Bugs that require external dependencies to fail (network down, disk full, clock skew)
- Resource lifecycle bugs that require sustained load to manifest
- Concurrency bugs in code paths protected by `example-auth-pro` (a black-box installed layer, out of scope). Concurrency bugs in FOSS-only code paths remain in scope.

## Integration-test catchable — definition

A bug is integration-test catchable if a reasonable end-to-end test — starts the server, makes real HTTP requests, observes real responses, inspects real database state — would have caught it with high probability.

This is the only criterion for the bug class. The challenger does not need to demonstrate user-visibility, severity, or any other property. The relevant question is: would integration testing have found it?

If yes, and our auto-generated suite did not — the claim is falsified for that category.

## What the framework publicly claims

The auto-generated suite catches:

1. **Vocabulary coverage.** Every member of every bounded vocabulary is fed through every chain that consumes it.
2. **Chain contracts.** Every valid output of link N is accepted as valid input by link N+1; a server fault at the downstream link flags a contract break.
3. **Purity.** Every link declared pure is verified deterministic, mutation-free, and free of I/O.
4. **Idempotency.** Every chain without boundary links produces identical results on identical input, twice.
5. **State machines.** Every (state, event) pair is exercised; undefined transitions fault correctly; adversarial state and event tokens are rejected.
6. **State invariants.** Every reachable post-state of every valid transition (including K-step sequences) satisfies all declared invariants.
7. **TOCTOU prevention.** Persist writes whose authorization depends on prior reads are fused into single guarded mutations. `honest-check` flags the un-fused pattern as auto-generation failure.
8. **Recognizer boundaries.** Adversarial neighbors of every valid token (edit-distance-1, Unicode confusables, control characters, length-extension) are confirmed to be rejected.
9. **Boundary isolation.** Non-boundary functions perform no I/O and access no non-deterministic sources.

The auto-generation also enforces, by structure:

- Every function has a declared role (`@link`, `@recognizer`, `@boundary`, `@helper`) or is reachable from a function with one. Orphan functions cause auto-generation to fail.
- Every chain has BDD feature coverage at the requirement level.
- Every dispatch table entry is exercised via the bounded vocabulary that drives it.

A challenger who introduces a bug that survives all of the above and is observable end-to-end via integration testing falsifies the claim for that bug's category.

## Bounty

**Tiered, first-finder per category, categories re-open after fix. Cash bounty payouts are contingent on grant funding being awarded; until funding lands, attribution is the operative incentive and submissions accumulate against the spec for retroactive payout once funding lands.**

| Tier | Finding | Bounty (once funded) |
|---|---|---|
| 1 | Bug whose category is a known framework claim | $50 first-finder |
| 2 | Bug whose category requires a new claim or a meaningful spec extension | $100 first-finder |

After a category falls:

1. Spec is patched to close the gap
2. Patched spec re-runs against the winning mutation; mutation must now fail pre-commit
3. Category re-opens against the patched spec, with a fresh $50 first-finder bounty (once funded)

Maximum exposure per round (once funded): ~$450. Realistic ongoing cost (once funded): ~$50–150/year once initial categories harden.

**The real prize is attribution, both pre-funding and post-funding.** The challenger's name appears on the permanent Methodology Falsifiers wall, in the spec changelog as the named credit for the fix, and in the next launch announcement. All challengers who attempt, including those whose submissions are rejected, appear on the wall with a "Tried" badge.

## Process

Every PR triggers automated CI in an isolated container. The pipeline runs `honest-check`, then the auto-generated `honest-test` suite, then BDD features, then a smoke run against a deployed instance. Any failure auto-closes the PR with the exact reason posted as a comment.

PRs that pass automation are labelled `pending-review` and routed to the panel with an auto-generated screen-recording of the running app under the mutation. The panel's only role is judging condition 4: would integration testing have caught this?

Winning submissions are published with full post-mortem: what was found, why the spec missed it, what the fix does, what adjacent mutations were considered. Each fall becomes a public document.

A real-time public leaderboard tracks: total submissions, surviving categories, days since last fall, named finders.

## Why this is the right challenge shape

The alternative — "break our security" or "find any obvious bug" — does not test the claim. The claim is specifically that the auto-generated pre-commit suite substitutes for integration testing.

The challenge must constrain the challenger to modify code that is exercised by the auto-generated suite (everything else is structurally rejected as dishonest), and measure whether the suite catches the mutation. The integration-test-catchable criterion narrows the bug class to exactly the population the claim is about.

A challenger who wins demonstrates an incompleteness in the test methodology. A challenge that runs open without a win for an extended period demonstrates the claim empirically.
