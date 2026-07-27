Feature: honest-estimate (implementation supplement)

  Scenario: _invoked_within collects every function a sibling invokes
    Given a module's IR
    When _invoked_within reads the invoke graph
    Then it returns the set of every name some sibling function invokes

  Scenario: _under_declared reports when a module fell back to the invoke graph
    Given a module's IR
    When _under_declared inspects its roles
    Then it is true only when the module has functions but no boundary or orchestrator role

  Scenario: _routed_targets collects the functions reached from the input boundary
    Given a module's IR
    When _routed_targets reads its routes and entries
    Then it returns the union of every route target and every entry target

  Scenario: _process_movements counts one process's data movements
    Given a function's IR
    When _process_movements maps its role and side effects
    Then it returns an Entry or eXit from the role plus a Read or Write per side effect, floored at two

  Scenario: _cardinalities reads the module's closed cardinalities
    Given a module's IR
    When _cardinalities reads its sets, vocabularies, and composed types
    Then it returns each set's member count, each vocabulary's sum over its referenced sets, and each composed type's fields

  Scenario: _head_atom reads a type's head atom
    Given a declared type
    When _head_atom reads it
    Then it returns the head atom's name, or the empty string when the type is empty

  Scenario: _bits_of measures one typed slot, recursing into composed types
    Given a type name and the module's cardinalities
    When _bits_of measures it
    Then it returns log-2 of a set or vocabulary, the sum over a composed type's fields, or zero with an open flag otherwise
    And a self-referential composed type is broken by the cycle guard and flagged, never recursed infinitely
