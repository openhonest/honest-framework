Feature: honest-parse — the shared parsing boundary
  One scenario per function. One function touches tree-sitter, one chooses the grammar from a
  path, one orchestrates the two, and the rest compute over the tree.

  Scenario: parse turns source into a syntax tree
    Given source text and the name of a supported language
    When parse reads it
    Then it returns the syntax tree for that source
    But a grammar this module does not carry is refused by name, saying which grammars it has

  Scenario: language_of names the grammar a path is read under
    Given a file path
    When language_of reads its extension
    Then it returns the grammar declared for that extension
    But an extension the table does not carry is refused, never read as the commonest grammar

  Scenario: place_source reads source under the grammar its path names
    Given source text and the path it came from
    When place_source asks which grammar the path names and reads the source under it
    Then it returns the syntax tree for that grammar
    But a path it cannot place is refused and the source is never read
    And source that does not parse is refused with a fault naming the line and column of the error

  Scenario: parse_source hands a calling module's call to the orchestrator
    Given a calling module with source text and the path it came from
    When parse_source receives the call
    Then it hands the call to the orchestrator and returns that answer unchanged


  Scenario: line_col reports a node's start position, counting from one
    Given a node
    When line_col reads its start
    Then it returns the line and column, each counted from one

  Scenario: walk returns every node, parents before children
    Given the root of a tree
    When walk traverses it
    Then it returns a list of every node in the subtree, each parent before its children
    But it answers a list, not a stream, so a second reader sees the same nodes

  Scenario: first_error_node finds the first broken place in a tree
    Given the root of a tree
    When first_error_node scans it
    Then it returns the first error or missing node, or nothing when the tree is clean
