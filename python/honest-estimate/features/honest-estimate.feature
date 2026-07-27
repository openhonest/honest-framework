Feature: honest-estimate (implementation supplement)

  Scenario: _routed_targets collects the functions reached from the input boundary
    Given a module's IR
    When _routed_targets reads its routes and entries
    Then it returns the union of every route target and every entry target

  Scenario: _param_type_name reads a parameter's head type atom
    Given a parameter's IR
    When _param_type_name reads its declared type
    Then it returns the head atom's name, or the empty string when the type is empty
