Feature: honest-state — generated, one scenario per function (8 total)

  Scenario: state_kinds
    Given no arguments
    When state_kinds is called
    Then it returns the whole taxonomy of §1.2 as data, one StateKind row per state kind, ten rows in all, each naming its kind, its home store and its single mutator
    And it takes no argument and reads nothing, the taxonomy being a fixed table of literals
    And every row names exactly one mutator, the acceptance test of §1.2 made true by construction
    And it is pure with no fault and no side effect

  Scenario: mutator_of
    Given kind: StateKindName
    When mutator_of is called
    Then it finds the StateKind row in the taxonomy whose kind equals the argument and returns that row's mutator prose
    And kind is one of the ten StateKindName words, so every value resolves to exactly one row with no miss and no fault
    And for 'persisted_domain' it returns the ordinary-boundary-write mutator and for 'composed_value' it returns the orchestrator, and so on for each of the ten
    And it invokes state_kinds to read the table rather than keeping a second copy of it

  Scenario: second_mutator_legitimate
    Given honest: bool and disjoint: bool
    When second_mutator_legitimate is called
    Then it returns true only when both honest and disjoint are true, the logical AND, and false otherwise
    And when honest is true and disjoint is true the second mutator is legitimate, admitting honest-alerts as a legitimate second mutator of the DOM
    And when honest is false, or disjoint is false, it returns false, rejecting any mutator that hides state or reaches into an owned region
    And it is pure with no fault and no side effect

  Scenario: names_one_mutator
    Given mutators: list<str>
    When names_one_mutator is called
    Then it returns true when the list names exactly one mutator and false otherwise
    And a false answer is the signal to split the candidate kind, not to allow two mutators
    And it is pure with no fault and no side effect

  Scenario: classify_dom_region
    Given source: RegionSource
    When classify_dom_region is called
    Then it dispatches the source word through dom_region_dispatch into exactly one of three classifications
    And a 'manifest_declared' region returns user_state, whose single mutator is the user
    And a 'server_driven' region returns server_state, whose single mutator is the server / alert source, a legitimate second mutator of the DOM
    And any 'other' region returns side_effect, a derived projection with no mutator of its own
    And source is one of the three RegionSource words, so it is pure with no fault and no side effect

  Scenario: user_state_region
    Given no arguments
    When user_state_region is called
    Then it returns the fixed classification 'user_state', the dom_region_dispatch handler for a manifest-declared region whose single mutator is the user
    And it takes no argument and returns a constant word, pure with no fault and no side effect

  Scenario: server_state_region
    Given no arguments
    When server_state_region is called
    Then it returns the fixed classification 'server_state', the dom_region_dispatch handler for a server/SSE-driven region whose single mutator is the server / alert source, honest and disjoint
    And it takes no argument and returns a constant word, pure with no fault and no side effect

  Scenario: side_effect_region
    Given no arguments
    When side_effect_region is called
    Then it returns the fixed classification 'side_effect', the dom_region_dispatch handler for any other region, a derived projection of user state and server state with no mutator of its own, re-derived and never written
    And it takes no argument and returns a constant word, pure with no fault and no side effect
