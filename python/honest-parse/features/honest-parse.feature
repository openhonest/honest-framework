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

  Scenario: parse_html parses source with the HTML template grammar
    Given HTML or HTMX template text
    When parse_html reads it
    Then it returns the syntax tree, using the HTML grammar

  Scenario: parse_jinja parses source with the Jinja template grammar
    Given Jinja template text
    When parse_jinja reads it
    Then it returns the syntax tree, using the Jinja grammar that surfaces include and extends targets

  Scenario: parse_css parses source with the CSS grammar
    Given CSS stylesheet text
    When parse_css reads it
    Then it returns the syntax tree, using the CSS grammar that surfaces the class selectors it defines

  Scenario: parse_hd parses source with the .hd architecture-declaration grammar
    Given .hd architecture-declaration text
    When parse_hd reads it
    Then it returns the syntax tree, using the hd grammar honest-design's reader folds into the IR
