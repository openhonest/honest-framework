Feature: honest-parse — Python supplement
  Scenarios that can only be stated in host-language terms. Counted toward the module's
  function points alongside the neutral scenarios in specs/features/honest-parse.feature.

  Scenario: parse_python parses source with the Python grammar
    Given Python source text
    When parse_python reads it
    Then it returns the syntax tree, using the Python grammar

  Scenario: parse_javascript parses source with the JavaScript grammar
    Given JavaScript source text
    When parse_javascript reads it
    Then it returns the syntax tree, using the JavaScript grammar

  Scenario: parse_ruby parses source with the Ruby grammar
    Given Ruby source text
    When parse_ruby reads it
    Then it returns the syntax tree, using the Ruby grammar

  Scenario: parse_php parses source with the PHP grammar
    Given PHP source text
    When parse_php reads it
    Then it returns the syntax tree, using the PHP grammar

  Scenario: parse_go parses source with the Go grammar
    Given Go source text
    When parse_go reads it
    Then it returns the syntax tree, using the Go grammar

  Scenario: parse_elixir parses source with the Elixir grammar
    Given Elixir source text
    When parse_elixir reads it
    Then it returns the syntax tree, using the Elixir grammar
