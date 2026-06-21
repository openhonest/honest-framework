Feature: honest-parse — Python supplement
  Scenarios that can only be stated in host-language terms. Counted toward the module's
  function points alongside the neutral scenarios in specs/features/honest-parse.feature.

  Scenario: parse_python parses source with the Python grammar
    Given Python source text
    When parse_python reads it
    Then it returns the syntax tree, using the Python grammar
