Feature: honest-gherkin — the parse contract (unit 1)
  One scenario per function; the scenario count is the module's directly-counted
  function-point size. Parsing is a fold over the lines: each line is sorted into one
  kind, then a pure handler updates the running state.

  Scenario: step_fault carries a parse fault as data
    Given a fault code and a detail message
    When step_fault builds it
    Then it returns a fault record, never a raised exception

  Scenario: _is_blank recognises an empty line
    Given a line
    When _is_blank checks it
    Then it answers yes only when the line is empty or all whitespace

  Scenario: _is_comment recognises a comment line
    Given a line
    When _is_comment checks it
    Then it answers yes when the first non-space character is a hash

  Scenario: _is_tag recognises a tag line
    Given a line
    When _is_tag checks it
    Then it answers yes when the first non-space character is an at-sign

  Scenario: _is_feature recognises the feature heading
    Given a line
    When _is_feature checks it
    Then it answers yes when the line begins the feature keyword

  Scenario: _is_scenario recognises a scenario heading
    Given a line
    When _is_scenario checks it
    Then it answers yes when the line begins the scenario keyword

  Scenario: _is_step recognises a step line
    Given a line
    When _is_step checks it
    Then it answers yes when the first word is one of the step keywords

  Scenario: _classify sorts a line into exactly one kind
    Given a line
    When _classify sorts it
    Then it returns the first matching kind in order, or description when none match

  Scenario: _flush moves the scenario under construction into the completed list
    Given the running state
    When _flush runs
    Then the scenario being built becomes a completed scenario, or the state is unchanged when there is none

  Scenario: _on_ignore leaves the state unchanged
    Given the running state and a blank or comment line
    When _on_ignore runs
    Then it returns the state untouched

  Scenario: _on_tag collects tags for the next scenario
    Given the running state and a tag line
    When _on_tag runs
    Then it adds each at-sign tag to the tags pending for the next scenario

  Scenario: _on_feature records the feature name
    Given the running state and a feature line
    When _on_feature runs
    Then it records the feature's name and marks the header open

  Scenario: _on_scenario starts a new scenario
    Given the running state and a scenario line
    When _on_scenario runs
    Then it flushes any scenario in progress and starts a new one with the pending tags
    But a scenario with no name is recorded as a bad-feature-syntax fault

  Scenario: _on_step adds a step to the current scenario
    Given the running state and a step line
    When _on_step runs
    Then it appends the step with its keyword, text, and the kind And or But inherits
    But a step outside any scenario is recorded as a bad-feature-syntax fault

  Scenario: _on_description collects the header description
    Given the running state and a non-keyword line
    When _on_description runs
    Then it adds the line to the description while the header is open
    But loose text outside a scenario is recorded as a bad-feature-syntax fault

  Scenario: parse_feature parses source into a feature
    Given gherkin source and its path
    When parse_feature reads it
    Then it returns the feature with its description, scenarios, and steps
    But malformed source returns a bad-feature-syntax fault rather than raising
