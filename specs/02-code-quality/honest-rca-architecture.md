# honest-rca: Architecture Specification

**Date:** July 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

honest-rca is the debugging expression of the framework's *via negativa*. It finds the root cause of a failure without lying about having found it. It never says "X is the root cause" — a positive claim about causation is unfalsifiable, because you can never demonstrate that nothing upstream contributed. It says the honest thing instead: *under a stated evidence set and a stated method, the causal chain terminates at X, and no upstream factor was identified.* That claim is falsifiable (widen the evidence or sharpen the method and an upstream factor may appear) and reproducible (re-run under the same evidence and method). It is the same epistemology as the gate — attest what cannot be found, bound the claim, state the limit. The methodology is in `methodology/root-cause-analysis.md`; this spec turns it into a module of pure functions.

## 1. Purpose and Scope

### 1.1 The abstract requirement

Given a precisely-stated failure, a bounded body of evidence, and a versioned causal method, honest-rca traces the causal chain to a fixpoint and emits a **bounded-completeness attestation**: a record that names the terminus, the evidence it searched, the method it used, the edges it could only judge (not ground), and the bound — what may lie outside the evidence or be invisible to the method. The attestation is the negative claim, never the positive one.

### 1.2 Which bug categories this eliminates (poka-yoke)

honest-rca exists to make a specific category of bug structurally impossible: **the fake root cause** — a positive, unbounded causal claim paired with a local patch ("it failed because `X` was `None`" → add a `None` check). Fake RCA is recognizable by what it omits: no evidence set, no method, no termination, no bound. It reads as done and usually is not — the *category* of failure stays reachable and the next instance wears a different mask.

The poka-yoke: a root-cause claim is representable in honest-rca only as an `Attestation`, and an `Attestation` is well-formed only when it carries its evidence hash, its method version, its terminus, its marked (judgment) edges, and its bound. A claim missing any of these is not a weaker attestation — it is not an `Attestation` at all; `validate_attestation` refuses it. The positive, unbounded claim has no representation. Additionally, when the terminus is a **design root** — a bug category, not an instance — the attestation is well-formed only when it names the category and the poka-yoke that closes it, enforcing the methodology's rule that a fix which cannot name the category it eliminates has not reached a design root.

### 1.3 Relationships

honest-rca composes three already-built modules and owns none of their concerns:

- **honest-observe** is where the evidence comes from. The unified event log and the canonical per-request record colocate control flow, queries, faults, and timing, so the causal graph is read from recorded fact rather than reconstructed by guess. honest-rca reads observe's records as evidence items; it does not emit or store events.
- **honest-parse / honest-check** ground the *deterministic* causal edges. A data-flow or control-flow dependency between two code sites is a parsed fact, not a judgment. honest-rca reads those relations; it does not re-parse.
- **poka-yoke** (`principles/poka-yoke.md`) is where a design-root terminus goes. honest-rca finds the fixpoint; the poka-yoke closes the category. honest-rca records the named category and the poka-yoke reference; it does not implement the fix.

### 1.4 What honest-rca covers

- The evidence set `E`: a bounded, snapshot-hashable body of evidence items.
- The method `M`: a versioned set of enabled causal signals and a traversal rule.
- The causal graph built by applying `M`'s signals to `E`.
- The fixpoint traversal from the symptom to the terminus `X`.
- The attestation: the bounded-completeness statement, and its validation.
- The bound: what lies outside `E` or is invisible to `M`, computed and stated.
- The design-root obligation: name the category and the poka-yoke.

### 1.5 What honest-rca does not cover

- Collecting evidence from the world (reading logs, running blame, querying traces) — that is boundary I/O; honest-rca operates on evidence items already assembled.
- Deciding the fix or applying it — honest-rca finds and bounds the terminus; poka-yoke design and the patch are elsewhere.
- Program analysis from scratch — the deterministic relations (data/control flow, change sets, timestamps) are read from parse/observe/history, not recomputed.

---

## 2. The Causal IR

Every value honest-rca handles is a plain record — data, no behaviour. The records are language-agnostic patterns; a language implementation realizes them as its idiomatic immutable record.

- **`Symptom`** — the observed failure, stated precisely and kept separate from any guess at its cause: `{id, description, site}` where `site` is the evidence-item id where the failure was observed. A `Symptom` names *what happened*, never *why*.
- **`EvidenceItem`** — one piece of the bounded evidence: `{id, kind, ref, precedes, flows_to, changed_with}`. `kind` is an evidence kind (§2.1). `ref` locates the item (a code site, an event id, a commit, a config key, a deploy-timeline entry). The three relation fields carry the *recorded* relations honest-rca grounds edges on, each a list of other item ids: `precedes` (temporal happens-before, from observe), `flows_to` (data/control-flow dependency, from parse), `changed_with` (co-change, from history). An item that carries no relation to a given node cannot be linked to it by a deterministic signal.
- **`EvidenceSet`** (`E`) — `{items, hash}`. `hash` is derived by `evidence_hash` (§3) and is the reproducibility key: the same items yield the same hash, and an attestation is re-verifiable only against the `E` its hash names.
- **`CausalEdge`** — a directed cause→effect link: `{cause, effect, signal, marked}`. `signal` is a signal kind (§2.1). `marked` is `true` exactly when `signal` is `judgment` — the "pseudo" in a pseudo-proof, reproducible only up to the judge's version. A grounded edge (`marked = false`) is a recorded fact; a marked edge is a reserved judgment.
- **`Method`** (`M`) — `{version, signals, traversal}`. `version` makes the method reproducible. `signals` is the set of enabled signal kinds (which grounds `M` will accept). `traversal` is the upstream-traversal rule (§6). More enabled deterministic signals means fewer marked edges means closer to a proof.
- **`CausalGraph`** — `{nodes, edges}` over `E`: the edges `M` produced from `E`'s recorded relations.
- **`Bound`** — the stated limit: `{outside_evidence, invisible_to_method}`. `outside_evidence` lists item ids referenced by the evidence but absent from `E` (a cause may lie there). `invisible_to_method` lists edges present by reference that no enabled signal could ground (a cause may hide in a signal `M` did not run). A `Bound` is always present, even when both lists are empty — an empty bound is a *stated* empty bound, not an omitted one.
- **`Attestation`** — the output, the negative claim: `{symptom, evidence_hash, method_version, terminus, chain, marked_edges, bound, category, poka_yoke}`. `terminus` is the node past which the bounded search finds nothing. `chain` is the traced path from symptom to terminus. `marked_edges` are the judgment edges the chain relied on. `bound` is the `Bound`. `category` and `poka_yoke` are present exactly when the terminus is a design root (§8). The record has no field that asserts "X is the root"; its semantics are fixed as the negative — *terminates at `terminus`; no upstream factor identified under `evidence_hash` and `method_version`.*

### 2.1 Bounded vocabularies

Three closed vocabularies make honest-rca exhaustively testable (honest-test builds the Cartesian product):

- **Evidence kinds:** `code`, `event`, `history`, `config`, `deploy`. The five sources the methodology names.
- **Signal kinds:** `dataflow`, `controlflow`, `change_correlation`, `temporal`, `judgment`. The first four are deterministic grounds; `judgment` is the marked, reserved-judgment edge.
- **Bound kinds:** `outside_evidence`, `invisible_to_method`. The two ways the bounded search can be incomplete.

---

## 3. Evidence Assembly and the Hash

`evidence_set(items) -> EvidenceSet` assembles a bounded evidence set and stamps its `hash`. `evidence_hash(items) -> str` is a pure, order-independent digest of the items: the same set of items in any order yields the same hash, and any change to an item's id, kind, ref, or relations changes it. The hash is what makes an attestation reproducible — re-deriving `E` and re-running `M` must reproduce the attestation exactly, and the hash is the key that proves the same `E` was searched.

Assembling the items from the world — reading observe's log, running blame, loading config — is boundary I/O and lives at the edge; `evidence_set` receives items already read.

---

## 4. The Method

`method(version, signals, traversal) -> Method` fixes a reproducible causal method. `M` is versioned because a marked (judgment) edge is reproducible only up to the judge's version; the attestation records `method_version` so a re-run is compared against the same method. `signals` is the enabled subset of the deterministic signal kinds plus, optionally, `judgment`; an edge whose signal is not enabled is not built. The more deterministic signals `M` enables, the more of the chain is grounded fact and the fewer edges are marked.

---

## 5. Edge Construction

`causal_graph(evidence, method) -> CausalGraph` builds the graph by applying each enabled signal's detector to `E`. The detectors are pure and dispatched by signal kind through a table, never an if/elif chain:

- **`dataflow_edges(evidence) -> [CausalEdge]`** — a grounded edge for each recorded `flows_to` relation whose direction is a data dependency: the cause's value reaches the effect. Read from parse.
- **`controlflow_edges(evidence) -> [CausalEdge]`** — a grounded edge where the cause's branch determines whether the effect executes. Read from parse.
- **`change_correlation_edges(evidence) -> [CausalEdge]`** — a grounded edge for each `changed_with` relation: the cause changed together with the failure. Read from history.
- **`temporal_edges(evidence) -> [CausalEdge]`** — a grounded edge for each `precedes` relation: strict happens-before in the event log. Read from observe.

Each detector emits only edges its signal can ground from the recorded relations; a relation absent from the evidence produces no edge. `judgment` builds no edges of its own — a judgment edge is supplied explicitly, `marked = true`, for a link no deterministic signal can settle, and it enters the graph only when `judgment` is enabled in `M`.

---

## 6. Fixpoint Traversal

`trace(graph, symptom, method) -> [id]` follows the graph upstream from the symptom's site, cause by cause, until it reaches a **fixpoint**: a node with no upstream cause that satisfies `M`. That node is the terminus `X` — not "the root," but the node past which this bounded search finds nothing. The traversal is deterministic and terminating: it never revisits a node (a cycle terminates at its entry, recorded as such), so it always reaches a fixpoint. The returned chain is the ordered path from the symptom to the terminus.

`terminus(chain) -> id` is the last node of a non-empty chain. When the symptom's site has no upstream edge at all, the chain is the symptom's site alone and the terminus is the symptom's site — a bounded search that found nothing upstream is itself an honest, if shallow, result.

---

## 7. The Attestation and Its Validation

`attest(symptom, evidence, method, chain) -> Attestation` assembles the negative claim: the terminus, the chain, the marked edges the chain relied on, and the bound (§7.1). It reads `evidence_hash` and `method_version` into the record so the claim carries its own reproducibility keys.

`validate_attestation(attestation) -> [fault]` is the poka-yoke guard. It returns a fault for each missing element of a well-formed bounded-completeness statement:

- a `missing_evidence_hash` fault when the evidence hash is empty,
- a `missing_method_version` fault when the method version is empty,
- a `missing_terminus` fault when there is no terminus,
- a `missing_bound` fault when the bound is absent (an *empty* bound is present and valid; an *absent* bound is not),
- a `missing_category` and/or `missing_poka_yoke` fault when the terminus is a design root but the category or poka-yoke is unnamed (§8).

An attestation for which `validate_attestation` returns no faults is a real RCA. One that omits its bound, its evidence, or its method is fake RCA, and it cannot pass. There is no positive-claim shape to validate — the fake claim is simply unrepresentable as a valid `Attestation`.

### 7.1 The bound is computed, not asserted

`bound(evidence, graph) -> Bound` derives the limit from fact. `outside_evidence` is the set of item ids that the evidence's relations reference but that are not themselves items in `E` — a cause may lie in one of them. `invisible_to_method` is the set of edges present by reference that no enabled signal grounded — a cause may hide in a signal `M` did not run. The bound is stated on the attestation's face; it is what makes the claim honest and checkable, exactly the discipline that a positive "X is the root" hides.

---

## 8. The Design Root and the Poka-Yoke

`terminus_is_design_root(item) -> bool` holds when the terminus is a design decision rather than an instance — a missing invariant, an unowned mutation, an unbounded input: a bug *category*. When it holds, the honest fix is the poka-yoke that makes the category unrepresentable, and the attestation must name both the category it eliminates and the poka-yoke that closes it. `validate_attestation` enforces this: a design-root attestation with no `category` or no `poka_yoke` fails. This is the methodology's rule made structural — a fix that cannot name the category it eliminates has not reached a design root, and honest-rca will not attest that it has.

---

## 9. honest-check Integration

honest-rca adds no new static rule of its own; the guard it needs is a *runtime* one and lives in `validate_attestation` (§7), because an attestation's completeness is a property of a produced value, not of source text — the same division honest-check and honest-test hold everywhere. The static surface honest-check already enforces (no classes, dict-dispatch, pure functions, I/O at the boundary) applies to honest-rca's own source unchanged.

---

## 10. honest-test Integration

Because the signal, evidence, and bound vocabularies are closed (§2.1), honest-test generates exhaustive tests automatically: every signal detector is exercised over evidence with and without its recorded relation; every evidence kind appears at a terminus; every way an attestation can be malformed is verified to produce its fault; and the bounded-completeness invariant is checked — the same `E` and `M` reproduce the same attestation. No developer input is required beyond the vocabularies.

---

## 11. Composition Contracts

- **reads observe:** evidence items of kind `event` carry `precedes` from observe's log ordering and request-id join; honest-rca never emits events.
- **reads parse/check:** evidence items of kind `code` carry `flows_to` from parse's data/control-flow facts; honest-rca never re-parses.
- **reads history:** evidence items of kind `history` carry `changed_with` from blame/change sets, assembled at the boundary.
- **feeds poka-yoke:** a design-root attestation names the category and references the poka-yoke; honest-rca does not implement the fix.

honest-rca imports none of these at runtime for its decision core; the evidence arrives as data assembled at the boundary, and the decision functions are pure over it.

---

## 12. Conformance

honest-rca's conformance is the apophatic discipline made checkable:

- `evidence_hash` is order-independent and change-sensitive; the same items reproduce the same hash.
- each deterministic signal detector emits exactly the grounded edges its recorded relation supports, and none where the relation is absent.
- `trace` reaches a fixpoint on every graph, including cyclic ones, and returns the symptom's site alone when nothing is upstream.
- `bound` lists every referenced-but-absent item and every ungrounded referenced edge, and an empty bound is stated, not omitted.
- `validate_attestation` returns no faults for a well-formed attestation and the precise fault for each omission, including the design-root category and poka-yoke obligations.
- the bounded-completeness invariant: a fixed `E` and `M` reproduce an identical attestation.

The conformance suite lives in the hub repo at `honest/honest-rca-conformance/suite.json`; its cases assert each contract above on planted evidence sets, and that no attestation asserts a positive "X is the root."
