# Rebuild harness: a deterministic loop over the four .hd agents

A note to resume from, written 2026-10-31. The idea is to turn the manual orchestration of the four-agent rebuild pipeline (hd-author, feature-author, test-author, honest-coder) into a deterministic harness, written in honest code, that calls each agent in turn and loops back on itself until no gap remains.

## Why it is now possible

Each of the four agents ends its report with a mandatory GAPS block, a typed return rather than prose. The shape is a `## Gaps` heading, then `GAPS: <n>`, then one `- <what was not fixed> (owner: spec|hd|feature|test)` line per gap, or `GAPS: 0 (...)` when clean. `owner` is a closed set, so it is a dispatch key. The harness reads the block instead of reading English, which is what makes the loop deterministic.

## The loop

The harness calls hd-author, then feature-author, then test-author, then honest-coder. After each agent it reads the GAPS block. For every gap line it dispatches on `owner` to the agent that owns that layer, feeds it the gap, and re-runs that layer and everything downstream of it. The loop ends when every layer returns `GAPS: 0`. That terminal state is a fixpoint.

Honest shape: dispatch on `owner` through a table, not an if/elif chain. The owner vocabulary bounds the key at construction, so an unmatched owner is a program bug and takes the no-match row.

## Two decisions still open (Adam has answers)

1. One owner has no agent. spec is normative and is Adam's call, so there is no spec-author to loop back to. The harness auto-closes hd, feature and test gaps by re-running those agents, but an `owner: spec` gap leaves the machine and halts for a person. This is the boundary, not a weakness.
2. The loop needs a termination guard. If feeding a gap to the layer above produces a new gap that regenerates the same one next pass, the loop does not converge, and that means the architecture permits the fault, per the standing rule that every failure must produce urgency to find its architectural cause. Bound the passes; when a gap recurs, stop and surface it as structural rather than spinning. A converging run is normal; a non-converging one is a finding.

## Current state

The four agent files in `~/.claude/agents/` carry the mandatory GAPS verdict. The pipeline memory `hd-rebuild-agent-pipeline` records the verdict and the routing. The first real run of the mechanism, on honest-check, produced five gaps, filed under epic `honest-framework-mct`:

- `honest-framework-eee` startup_check: spec names no startup-eligible rule or source that emits a blocking error-severity finding (owner: spec)
- `honest-framework-zo5` check_source: no per-rule function-point, so no test can pin a specific rule's Diagnostic (owner: spec/hd)
- `honest-framework-lyd` read_source: no fault declared for a missing or unreadable path (owner: hd/spec)
- `honest-framework-x1g` load_config: full default map and honest-check.toml override syntax not pinned (owner: hd/spec)
- `honest-framework-v7j` check_paths: "load_config pulled once" unobservable without a mock; exact diagnostics not fixed (owner: feature/hd)

Next step when we resume the harness itself: draft it as an honest module, a dispatch table keyed on `owner`, with the two decisions above settled.

## Guards added after the first run (2026-11-01)

The first run reached green with a hollow module. honest-check passed its five scenarios with one rule of thirty built, because the tests could not fail and the declaration hid the engine. The RCA found two roots. The declaration hid the engine and omitted what the input is (Root A). The gap-verdict guard fired at the test and code layers and the orchestrator waved it off (Root B). Five guards remove those roots, and the harness enforces the mechanical ones.

1. Stub-survival gate (mechanical, in honest-coder). Before the coder builds, every function is a trivial stub and the whole suite runs. The suite must go red. A probe that passes against a stub tests nothing and loops back to the test layer. This is mutation-adequacy at rebuild time, and it removes Root B's consequence without any judgement.
2. No vacuous tests (test-author rule, enforced by guard 1). A behavioural probe pins at least one literal non-trivial input-to-output case. A shape-only assertion, and an oracle that recomputes from the function under test, are both banned for the behavioural claim.
3. Declare the folded set as data (hd skill and hd-author rule). A function that "runs every registered rule" declares the rules as a `set` or `vocabulary` and the selection as a `dispatch`, so the declaration names and counts them instead of hiding them in prose.
4. State every opaque input's domain (hd-author rule). A `str`, `bytes`, `any` or `handle` input states in its note what artifact it holds, so a downstream author never has to guess what the value is.
5. No non-actionable bucket (harness rule). Every GAPS line with an owner loops to that owner. `hd`, `feature` and `test` loop to the agent; `spec` halts for the human. The orchestrator may not classify a flagged gap away. The only exits are GAPS zero everywhere or a human decision.

Guards 1, 2 and 5 hold even when a note is wrong or the orchestrator is careless, so they are the ones the harness cannot ship without.
