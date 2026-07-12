Feature: honest-features — runtime feature flags as a static vocabulary and a threaded state value

  Scenario: validate_vocabulary checks each flag's states and initial value
    Given a flag vocabulary
    When validate_vocabulary checks it
    Then a flag whose entry is not exactly states and initial_value, or has fewer than two distinct states, or an initial_value outside them, is a client fault, never a raise

  Scenario: _flag_wellformed checks one flag entry's structure and contents
    Given one flag entry
    When _flag_wellformed inspects it
    Then it holds only when the entry has exactly states and initial_value, a collection of at least two distinct states, and a member initial_value

  Scenario: initial_state builds the startup state from the initial values
    Given a flag vocabulary
    When initial_state is built
    Then every flag holds its declared initial value

  Scenario: feature_state reads a flag from the state value
    Given a flag state value
    When feature_state reads a flag
    Then it returns that flag's current state

  Scenario: validate_toggle checks the flag and state of a request
    Given a toggle request for a flag and a state
    When validate_toggle checks it
    Then an undeclared flag or an undeclared state is a client fault

  Scenario: apply_toggle returns the previous state and a new state value
    Given a held state value and a flag set to a new state
    When apply_toggle is applied
    Then it returns the previous state and a new state value with the flag updated

  Scenario: build_signature signs a toggle with HMAC-SHA256
    Given a shared secret and a flag, state, and timestamp
    When build_signature signs them
    Then it returns the HMAC-SHA256 hexdigest over the message

  Scenario: verify_signature rejects tampered or replayed toggles
    Given a signed toggle and an injected current time
    When verify_signature checks it
    Then it accepts only a matching signature within the replay window

  Scenario: changed_event records a successful toggle
    Given a completed toggle
    When changed_event is built
    Then it is the hf.features.changed payload for honest-observe

  Scenario: evaluated_event records a flag read in request context
    Given a flag read during a request
    When evaluated_event is built
    Then it is the hf.features.evaluated payload for honest-observe
