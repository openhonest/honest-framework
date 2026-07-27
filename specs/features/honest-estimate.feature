Feature: honest-estimate — deductive size from the .hd contract boundary

  Scenario: size reads a .hd module and reports its deductive size
    Given the source text of one .hd module
    When size reads it
    Then it returns the process breadth, the bits of case-distinction, and the open-vocabulary flags, wrapped in a result
    And a malformed source returns the read fault, and a module-less source a no_module fault, never raised

  Scenario: elementary_processes lists a module's boundary contracts
    Given a module's IR
    When elementary_processes applies the widened rule
    Then it returns every boundary or orchestrator role, and every pure function no sibling invokes
    And an invoked pure function is an interior helper and is not counted

  Scenario: breadth counts the processes and splits the IFPUG-countable subset
    Given a module's IR
    When breadth counts its elementary processes
    Then it reports the total, the routed user-facing subset, the beyond-IFPUG internal rest, and the internal share

  Scenario: depth sums bits of case-distinction over closed vocabularies
    Given a module's IR
    When depth walks each process's parameters
    Then a parameter typed by a declared set contributes log-2 of its cardinality
    And a parameter of any other type is flagged open and contributes nothing
