Feature: honest-parse — the shared parsing boundary
  One scenario per function. The language-neutral behaviour of the parsing layer; the
  host-language grammar convenience wrapper lives in the python supplement.

  Scenario: parse turns source into a syntax tree
    Given source text and the name of a supported language
    When parse reads it
    Then it returns the syntax tree for that source
    But an unsupported language is refused

  Scenario: node_text returns the exact source a node spans
    Given a node and the source it came from
    When node_text reads it
    Then it returns exactly the slice of source the node covers

  Scenario: line_col reports a node's start position, counting from one
    Given a node
    When line_col reads its start
    Then it returns the line and column, each counted from one

  Scenario: walk visits every node, parents before children
    Given the root of a tree
    When walk traverses it
    Then it yields every node in the subtree, each parent before its children

  Scenario: first_error_node finds the first broken place in a tree
    Given the root of a tree
    When first_error_node scans it
    Then it returns the first error or missing node, or nothing when the tree is clean
