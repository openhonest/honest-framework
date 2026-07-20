Feature: honest-rca — the apophatic root-cause solver

  One scenario per function point. honest-rca traces a failure through a bounded, hashable
  evidence set under a versioned method, to a fixpoint, and attests the negative — never
  "X is the root cause", always "under this evidence and method, the chain terminates at X
  and no upstream factor was found". The bound is stated; fake RCA is unrepresentable.

  Scenario: evidence_hash digests an evidence set order-independently and change-sensitively
    Given a list of evidence items
    When evidence_hash digests them
    Then the same items in any order yield the same hash and any changed field changes it

  Scenario: evidence_set assembles the bounded evidence and stamps its hash
    Given a list of evidence items
    When evidence_set assembles them
    Then it carries the items and the reproducibility hash

  Scenario: causal_edge builds a directed cause-to-effect edge marking judgment edges
    Given a cause, an effect, and a signal kind
    When causal_edge builds the edge
    Then it is marked exactly when the signal is judgment

  Scenario: dataflow_edges grounds an edge for each recorded data-flow relation
    Given evidence items carrying flows_to relations
    When dataflow_edges reads them
    Then it grounds one dataflow edge per relation and none where the relation is absent

  Scenario: controlflow_edges grounds an edge for each recorded control-flow relation
    Given evidence items carrying controls relations
    When controlflow_edges reads them
    Then it grounds one controlflow edge per relation and none where the relation is absent

  Scenario: change_correlation_edges grounds an edge for each recorded co-change relation
    Given evidence items carrying changed_with relations
    When change_correlation_edges reads them
    Then it grounds one change_correlation edge per relation and none where the relation is absent

  Scenario: temporal_edges grounds an edge for each recorded happens-before relation
    Given evidence items carrying precedes relations
    When temporal_edges reads them
    Then it grounds one temporal edge per relation and none where the relation is absent

  Scenario: causal_graph applies the enabled signals and adds judgments only when enabled
    Given an evidence set, a method, and proposed judgment edges
    When causal_graph builds the graph
    Then it holds the grounded edges of the enabled signals plus judgments only when judgment is enabled

  Scenario: trace follows the graph upstream to a fixpoint
    Given a causal graph and a symptom
    When trace follows causes upstream
    Then it returns the ordered chain from the symptom to a fixpoint, revisiting no node

  Scenario: terminus is the last node of the chain
    Given a chain
    When terminus is read
    Then it returns the last node, or empty for an empty chain

  Scenario: bound states what lies outside the evidence and invisible to the method
    Given an evidence set and a graph
    When bound is computed
    Then it lists referenced-but-absent items and recorded relations no enabled signal grounded

  Scenario: terminus_is_design_root holds when the item names a bug category
    Given an evidence item
    When terminus_is_design_root is asked
    Then it holds exactly when the item carries a non-empty category

  Scenario: attest assembles the bounded-completeness statement
    Given a symptom, an evidence set, a method, a graph, a chain, and a poka-yoke
    When attest assembles the attestation
    Then it carries the terminus, chain, marked edges, bound, category, and reproducibility keys

  Scenario: validate_attestation refuses an attestation missing any element of the negative claim
    Given an attestation
    When validate_attestation checks it
    Then it faults a missing hash, method version, terminus, bound, or a design root without a poka-yoke
