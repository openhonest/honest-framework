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

  # compile
  Scenario: compile_pattern turns a step pattern into an anchored matcher
    Given a step pattern with optional placeholders, written {name} or {name:type}
    When compile_pattern compiles it
    Then it returns an anchored matcher with one named capture per placeholder, recording each capture's type
    But an unknown placeholder type returns a bad-feature-syntax fault rather than raising

  # registry
  Scenario: empty_registry is a registry value with no patterns
    Given nothing
    When empty_registry is called
    Then it returns a registry holding an empty list of patterns, never a global

  Scenario: register_step adds one pattern without mutating its argument
    Given a registry, a step kind, a pattern, and a handler
    When register_step adds them
    Then it returns a new registry with the pattern appended in order
    But the registry passed in is left unchanged

  Scenario: _coerce_captures binds each capture to its recorded type
    Given a regex match and the captures recorded for a pattern
    When _coerce_captures binds them
    Then each named value is coerced to its recorded type, so an int reads as an int rather than a string

  Scenario: match_step resolves a step against the registry
    Given a step and a registry of patterns
    When match_step matches the step
    Then exactly one matching pattern returns the match with its captures coerced
    But no match returns a step-unmatched fault and more than one returns an ambiguous-step fault

  # run
  Scenario: _now_ms reads the wall clock in milliseconds
    Given the running engine
    When _now_ms is read
    Then it returns the current wall-clock time in milliseconds, the one impure seam in the run model

  Scenario: _classify_exception sorts a caught handler exception into the fault vocabulary
    Given an exception caught at the handler boundary
    When _classify_exception sorts it
    Then an assertion failure becomes failed with assertion-failed, and any other exception the catch-all errored with step-errored

  Scenario: run_step matches a step and classifies its outcome
    Given a step, the running context, and a registry
    When run_step runs the step
    Then a matched, successful handler returns ok with the new context, a falsey return keeps the context unchanged
    But an unmatched or ambiguous match, an assertion, or any other exception each becomes its own non-ok status carried as data

  Scenario: run_scenario folds the steps over an empty immutable context
    Given a scenario, its background steps, and a registry
    When run_scenario runs them
    Then it folds background then own steps over an empty context, threading a new context on each success, stopping at the first non-ok step
    But the scenario status is ok only when every executed step is ok

  Scenario: fold_feature_report combines scenario reports into a feature report
    Given a feature and its scenario reports
    When fold_feature_report combines them
    Then it counts the ok scenarios as passed and the rest as failed, carrying the feature name and path
