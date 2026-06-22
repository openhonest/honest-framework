Feature: honest-test — Python supplement
  Scenarios that can only be stated in host-language terms: walking the Python syntax tree to
  read length bounds and classify predicates, reading a live function's source, and parsing
  the configuration file. Counted toward the module's function points alongside the neutral
  scenarios in specs/features/honest-test.feature.

  Scenario: _is_len_call recognises a length call in the syntax tree
    Given a syntax-tree node and the source it came from
    When _is_len_call inspects it
    Then it reports true only when the node calls the length builtin

  Scenario: _int_value reads an integer literal from the syntax tree
    Given a syntax-tree node and the source it came from
    When _int_value reads it
    Then it returns the integer value when the node is an integer literal, otherwise nothing

  Scenario: _bound_from_pair derives a length bound from one comparison
    Given the left node, the operator, the right node, the source, and the bounds so far
    When _bound_from_pair inspects the comparison
    Then it records a bound when one side is a length call and the other an integer literal
    And it flips the operator when the length call is on the right
    But any other comparison contributes nothing

  Scenario: _scan_comparison derives bounds from a chained comparison
    Given a comparison node, the source, and the bounds so far
    When _scan_comparison flattens it into operand-operator-operand triples
    Then it derives a bound from each adjacent triple

  Scenario: extract_length_bounds reads the allowed length range from predicate source
    Given the source text of a predicate
    When extract_length_bounds walks its syntax tree for length comparisons
    Then it returns the minimum and maximum length the predicate allows
    And the minimum defaults to one and the maximum is absent when there is no upper bound

  Scenario: _callee_identifier records the fact a bare-name call signals
    Given a callee identifier node, the source, and the facts so far
    When _callee_identifier inspects the name
    Then it records the mapped fact for a recognised builtin
    And it records an unrecognised, non-ignored name as a named call

  Scenario: _callee_attribute records a character-class fact from a method call
    Given a callee attribute node, the source, and the facts so far
    When _callee_attribute inspects the attribute
    Then it records the character-class fact when the method is a character-class test

  Scenario: _fact_call routes a call node to the right callee handler
    Given a call node, the source, and the facts so far
    When _fact_call reads the callee
    Then it dispatches an identifier or attribute callee to its handler, ignoring others

  Scenario: _fact_comparison records that the source compares values
    Given a comparison node, the source, and the facts so far
    When _fact_comparison reads it
    Then it records that a comparison is present

  Scenario: _fact_numeric_literal records that the source contains a number
    Given a numeric-literal node, the source, and the facts so far
    When _fact_numeric_literal reads it
    Then it records that a numeric literal is present

  Scenario: _fact_true records that the source is an always-true predicate
    Given a true-literal node, the source, and the facts so far
    When _fact_true reads it
    Then it records the catch-all fact

  Scenario: _collect_facts gathers every classification fact from predicate source
    Given the source text of a predicate
    When _collect_facts walks its syntax tree
    Then it returns the facts found, with the numeric fact set when a numeric call appears or a comparison meets a numeric literal

  Scenario: classify_source classifies a predicate from its source text
    Given the source text of a predicate and the set of codebase names
    When classify_source weighs the facts by precedence
    Then it returns the most specific self-contained class, or composite for a known codebase call, external for an unknown call, and unknown otherwise

  Scenario: classify_predicate classifies a live predicate by reading its source
    Given a live predicate recognizer or callable and the set of codebase names
    When classify_predicate reads the function's source and classifies it
    Then it returns the class from the source
    But a function whose source cannot be read is treated as external

  Scenario: load_config reads and parses the configuration file
    Given the path to the configuration file
    When load_config reads it
    Then it returns the parsed contents using the standard-library parser
    But it returns an empty configuration when the file is absent

  Scenario: _bound_registry builds a per-case registry that binds the case data directly
    Given a value case and the function map
    When _bound_registry builds the registry
    Then it registers the supply-input, call-function, and assert-oracle steps with the concrete data bound directly, resolving the function inside the step so an unknown name surfaces as a caught fault
