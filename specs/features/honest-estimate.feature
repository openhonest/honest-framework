Feature: honest-estimate — deductive SIZE from the .hd contract boundary

  Scenario: size reads a .hd module and reports its three deductive size readings
    Given the source text of one .hd module
    When size reads it
    Then it returns the COSMIC CFP, the VFP breadth, the bits of case-distinction, and the open-vocabulary flags, wrapped in a result
    And a malformed source returns the read fault, and a module-less source a no_module fault, never raised
    And CFP is reported uncertified until the COSMIC mapping is validated

  Scenario: elementary_processes lists a module's boundary contracts
    Given a module's IR
    When elementary_processes applies the role-authority rule
    Then where any boundary or orchestrator role is declared, the processes are exactly the role-bearing functions
    And where no role is declared, the invoke-graph fallback treats a pure function no sibling invokes as a contract

  Scenario: vfp counts the processes and splits the IFPUG-countable subset
    Given a module's IR
    When vfp counts its elementary processes
    Then it reports the total, the routed user-facing subset, the beyond-IFPUG internal rest, the internal share, and whether the count used the fallback

  Scenario: cfp sums the COSMIC data movements over the elementary processes
    Given a module's IR
    When cfp maps each process's role and side effects to data movements
    Then it sums an Entry or eXit from the role and a Read or Write per side effect, flooring each process at two movements

  Scenario: depth sums bits of case-distinction over closed vocabularies and composed types
    Given a module's IR
    When depth walks each process's input parameters
    Then a parameter typed by a set or vocabulary contributes log-2 of its cardinality, a composed type the sum of its fields' bits
    And a parameter of any other type is flagged open and contributes nothing
