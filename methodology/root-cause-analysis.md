# Root-Cause Analysis: Attesting the Negative

How to find the root cause of a failure without lying about having found it — the framework's *via negativa* (apophasis) applied to debugging. See the framework spec, "Apophasis: correctness attested by refusal," for why this is the same method as the gate.

## Why This Exists

Fake root-cause analysis stops at the **proximate** cause and asserts it *is* the root: "it failed because `X` was `None`." That is a **positive** claim — "X is the root cause" — and a positive claim about causation is unfalsifiable: you can never demonstrate that nothing upstream contributed. Language models and hurried engineers stop there precisely because a positive assertion needs no proof of completeness. It reads as done. It usually is not — the *category* of failure stays reachable, and the next instance wears a different mask.

True RCA makes the apophatic move instead. You do not claim to have found *the* root. You attest the **negative**: under a stated evidence set `E` and method `M`, no further upstream causal factor could be identified; the causal chain terminates at `X`. That claim is **falsifiable** (widen `E` or sharpen `M` and an upstream factor may appear) and **reproducible** (re-run under the same `E`, `M`). It is the same epistemology as the gate: attest what cannot be found, bound the claim, state the limit.

## The Solver

1. **State the observed failure precisely** — the symptom, kept separate from any guess at its cause.
2. **Assemble the evidence set `E`** — the bounded body of evidence the search runs over: the code, its history (blame), traces and logs, config, the deploy timeline. `E` is snapshot-hashable; the same `E` must be re-derivable.
3. **Fix the method `M`** — the causal-link predicate ("A caused B") and the traversal rule, **versioned**. Ground each edge in a **deterministic** signal wherever one exists: a data- or control-flow dependency, a change correlation (this edge changed together with the failure), temporal precedence. Reserve judgment — a model's or a human's — only for edges no deterministic signal can settle, and **mark those edges**. A marked edge is the "pseudo" in a pseudo-proof: reproducible only up to the judge's version. The more of `M` is deterministic, the closer the result is to a proof.
4. **Trace to a fixpoint** — follow `M` upstream through `E` until no node upstream of the current one satisfies `M`. The chain terminates at `X`. `X` is not "the root"; `X` is the node past which *this bounded search* finds nothing.
5. **Attest the negative** — the output is a bounded-completeness statement, not a verdict: *under `E` (hash) and `M` (version), the causal chain terminates at `X`; no upstream factor was identified.* Verifiable by re-run.

## The Bound Is a Feature, Not a Caveat

The true cause may lie **outside `E`** — a vendor's behaviour, a human decision, a hardware fault — or be **invisible to `M`** — an edge no available signal can ground. The attestation says so. You are attesting the completeness of a *bounded* search, never omniscience. Stating the limit is not a weakness of the claim; it is what makes the claim honest and checkable. A positive "X is the root" hides its bound and so cannot be verified; the apophatic claim wears its bound on its face.

## The Terminus and the Fix

When `X` is a design decision — a missing invariant, an unowned mutation, an unbounded input — it is a bug **category**, and the honest fix is the poka-yoke that makes the category unrepresentable (`principles/poka-yoke.md`: *which category of bug does this make structurally impossible?*), not a patch on the instance. The apophatic RCA finds the fixpoint; the poka-yoke closes it. A fix that cannot **name the category it eliminates** has not reached a design root — it has patched a proximate cause, and the search should continue.

The framework's own observability is where `E` comes from: honest-observe's unified event log and canonical per-request record colocate the control flow, the queries, the faults, and the timing, so the causal graph is read from recorded fact rather than reconstructed by guess.

## The Anti-Pattern: Fake RCA

The tell is a positive, unbounded claim paired with a local patch: "it failed because `X` was `None`" → add a `None` check. The claim names no `E`, no `M`, no termination; the fix leaves every other path that could produce `None` untouched. Fake RCA is recognizable by what it **omits** — the bound. If an analysis does not state the evidence it searched and the method it used, it has not done RCA; it has guessed and stopped.

## Checklist

Before calling a cause "root":

- [ ] The symptom is stated precisely, separate from any cause.
- [ ] `E` is stated and hashable — code, history, traces, config, timeline.
- [ ] `M` is stated and versioned; deterministic edges are grounded; judgment edges are marked.
- [ ] The chain is traced to a fixpoint — no upstream node satisfies `M`.
- [ ] The claim is the **negative** — "under `E`, `M`, terminates at `X`; no upstream factor identified" — not "X is the root."
- [ ] The bound is stated — what may lie outside `E` or be invisible to `M`.
- [ ] At a design root, the fix is the poka-yoke that eliminates the category, and the category is named.
