Feature: honest-state — the single-mutator law and the taxonomy of state kinds

  Scenario: state_kinds lists the kinds of state with their store and mutator
    Given the framework's taxonomy of state
    When state_kinds is asked
    Then it returns every kind with the store it lives in and its single mutator

  Scenario: mutator_of names the single mutator that owns a kind
    Given a kind of state
    When mutator_of is asked
    Then it returns that kind's single mutator, or an unknown_state_kind fault

  Scenario: second_mutator_legitimate decides whether a second mutator is allowed
    Given whether a second mutator is honest and whether it is disjoint
    When second_mutator_legitimate decides
    Then a second mutator is legitimate only when it is both honest and disjoint
