Feature: honest-rca — generated, one scenario per function (16 total)

  honest-rca is the apophatic root-cause solver (spec §1). It builds a causal graph from a
  bounded, hashable evidence set under a versioned method, traces upstream to a fixpoint, and
  attests the negative — never "X is the root", only "under this evidence hash and this method
  version the chain terminates at X and no upstream factor was identified". Its decision core is
  a ring of pure functions, but the module is not a pure leaf: it declares foreign-shaped records
  and so owns a seam with one door, diagnose, that hands its inputs to the one orchestrator,
  run_rca. No pure function reads a file, clock, network or environment, and nothing raises;
  faults travel back by return. Each scenario's subject is a declared function; the Then is drawn
  from that function's .hd note.

  Scenario: evidence_hash
    Given items: list<EvidenceItem>
    When evidence_hash is called
    Then it returns a string digest of the items that is order-independent, so the same set of items in any order yields the same hash, and change-sensitive, so any change to an item's id, kind, ref, or relations changes it; the hash is the reproducibility key that proves the same evidence was searched; it reads no world and raises nothing

  Scenario: evidence_set
    Given items: list<EvidenceItem>
    When evidence_set is called
    Then it returns an EvidenceSet whose items are the given items and whose hash is evidence_hash(items); it does no collection of its own, because reading the log, running blame, and loading config are boundary I/O that happen at the edge before the items are passed in; it is pure and raises nothing

  Scenario: relation_flows_to
    Given item: EvidenceItem
    When relation_flows_to is called
    Then it returns the item's flows_to relation — the downstream item ids whose value depends on this item, grounded from parse's data-flow facts — and returns an empty list where the relation is absent, which yields no edge; it is pure and raises nothing

  Scenario: relation_controls
    Given item: EvidenceItem
    When relation_controls is called
    Then it returns the item's controls relation — the downstream item ids whose execution this item's branch gates, grounded from parse's control-flow facts — and returns an empty list where the relation is absent, which yields no edge; it is pure and raises nothing

  Scenario: relation_changed_with
    Given item: EvidenceItem
    When relation_changed_with is called
    Then it returns the item's changed_with relation — the downstream item ids that changed together with this item, grounded from history's blame/change sets — and returns an empty list where the relation is absent, which yields no edge; it is pure and raises nothing

  Scenario: relation_precedes
    Given item: EvidenceItem
    When relation_precedes is called
    Then it returns the item's precedes relation — the downstream item ids this item strictly happens-before in the event log, grounded from observe's log ordering — and returns an empty list where the relation is absent, which yields no edge; it is pure and raises nothing

  Scenario: signal_edges
    Given evidence: EvidenceSet and kind: SignalKind
    When signal_edges is called
    Then it dispatches on kind through the by_signal table to pick the relation detector, applies that detector to each item in the evidence, and emits one CausalEdge for each downstream id the relation names, with cause the item's id, effect the downstream id, signal the kind, and marked false because a grounded edge is a recorded fact; it emits only edges its signal can ground, so an absent relation produces no edge and it returns an empty list where the relation is empty throughout; it is pure and raises nothing

  Scenario: causal_graph
    Given evidence: EvidenceSet and method: Method and judgments: list<CausalEdge>
    When causal_graph is called
    Then for each deterministic signal kind enabled in method.signals it calls signal_edges(evidence, kind) and collects the grounded edges, then adds the supplied judgments only when judgment is enabled in method.signals, so an edge whose signal is not enabled is not built; the returned CausalGraph's nodes are the evidence items' ids and its edges are the grounded edges plus the enabled judgments, scoping the graph to exactly what the method grounds or enables; it is pure and raises nothing

  Scenario: trace
    Given graph: CausalGraph and symptom: Symptom
    When trace is called
    Then it follows the graph upstream from the symptom's site, cause by cause, and returns the ordered chain of item ids from the site to the terminus — the node with no upstream cause that satisfies the method; the traversal is deterministic and terminating, never revisiting a node, so a cycle terminates at its entry and it always reaches a fixpoint; when the site has no upstream edge at all, the returned chain is the site alone; it is pure and raises nothing

  Scenario: terminus
    Given chain: list<str>
    When terminus is called
    Then it returns the final id of a non-empty chain — not "the root", but the node past which this bounded search finds nothing — and when the chain is the symptom's site alone, the terminus is that site; it is pure and raises nothing

  Scenario: bound
    Given evidence: EvidenceSet and graph: CausalGraph
    When bound is called
    Then it returns a Bound whose outside_evidence is the set of item ids the evidence's relations reference but that are not themselves items in the evidence set (a cause may lie in one of them), and whose invisible_to_method is the set of referenced edges that no enabled signal grounded (a cause may hide in a signal the method did not run); the bound is always returned, even when both lists are empty, because an empty bound is stated rather than omitted; it is pure and raises nothing

  Scenario: attest
    Given symptom: Symptom and evidence: EvidenceSet and method: Method and graph: CausalGraph and chain: list<str> and poka_yoke: str
    When attest is called
    Then it reads the evidence's hash into evidence_hash and the method's version into method_version, reads the marked judgment edges the chain relied on from the graph, calls terminus(chain) for the terminus id and bound(evidence, graph) for the Bound, copies the terminus item's category (empty for an ordinary terminus, the named bug category for a design root), copies the supplied poka_yoke, and assembles all of these into an Attestation; it reads no world and raises nothing, because a construction failure is caught by validate_attestation, not by a raise here

  Scenario: validate_attestation
    Given attestation: Attestation
    When validate_attestation is called
    Then it returns a list of honest-type Fault values, one for each missing element, and an empty list for a real RCA: a missing_evidence_hash fault when the evidence hash is empty, a missing_method_version fault when the method version is empty, a missing_terminus fault when there is no terminus, a missing_bound fault when the bound is absent (an empty bound is present and valid, an absent bound is not), and a missing_poka_yoke fault when the terminus is a design root (a non-empty category) but no poka_yoke is named; it is pure and returns its faults as data, never raising

  Scenario: terminus_is_design_root
    Given item: EvidenceItem
    When terminus_is_design_root is called
    Then it returns true exactly when the item carries a non-empty category — when the terminus is a design decision (a missing invariant, an unowned mutation, an unbounded input, a bug category) rather than a single instance — and false for an ordinary item; it is a pure predicate that reads no world and raises nothing

  Scenario: run_rca
    Given symptom: Symptom and items: list<EvidenceItem> and method: Method and judgments: list<CausalEdge> and poka_yoke: str
    When run_rca is called
    Then it is the one orchestrator, the sequenced RCA path: it takes the inputs the door hands it and runs the pure steps in order, passing each its inputs — evidence_set(items) builds the hashed EvidenceSet, causal_graph(evidence, method, judgments) builds the CausalGraph over that set under the method's enabled signals plus the supplied judgment edges, trace(graph, symptom) follows the graph upstream from the symptom's site to the terminus and returns the chain, attest(symptom, evidence, method, graph, chain, poka_yoke) assembles the Attestation, and validate_attestation(attestation) checks it is a well-formed bounded-completeness statement; symptom is the precise failure the host was handed, items is the EvidenceItem list the host already read at the boundary (run_rca does no collection itself), method is the versioned Method whose signals field names the enabled signal kinds, judgments is the supplied list of marked judgment edges added to the graph only when judgment is enabled in the method, and poka_yoke is the poka-yoke reference for a design-root terminus or the empty string for an ordinary one; it returns the Attestation when validate_attestation finds no faults (a real RCA) and the list of Faults otherwise, so a malformed construction comes back as named data and never as a positive "X is the root" claim; it is pure orchestration, reads no side of the world and raises nothing, carrying validate_attestation's faults back by return

  Scenario: diagnose
    Given symptom: Symptom and items: list<EvidenceItem> and method: Method and judgments: list<CausalEdge> and poka_yoke: str
    When diagnose is called
    Then it is the composition root, the one door, a host-called entry like honest-page's create_app: the host assembles the evidence from honest-observe's log, honest-parse/check's flow facts, and version history, and takes the person's Symptom and the config Method — all boundary I/O that lives outside honest-rca — then calls diagnose with it already in hand; diagnose does no collection and reads no side of the world, it hands the assembled inputs straight to run_rca and returns what run_rca returns; symptom is the person's precise statement of the failure, items is the already-read list of EvidenceItem values the host assembled at the boundary, method is the versioned Method with its enabled signal set and traversal rule, judgments is the supplied list of marked judgment edges, and poka_yoke is the poka-yoke reference for a design-root terminus or the empty string otherwise; it returns the Attestation — the bounded-completeness negative claim — when the attestation is well-formed, or the list of Faults validate_attestation named when it is not, carrying that fault back by return rather than raising, because a malformed attestation is data the host reads, not a condition that must stop the world
