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

  Scenario: depth sums bits and cases over the closed vocabularies a process commits to
    Given a module's IR
    When depth gathers, for each process, the distinct closed vocabularies on its inputs, on its own eXit return, and on the returns of the pure functions or readers it dispatches on
    Then it sums log-2 of each vocabulary's cardinality as bits and the cardinalities themselves as cases, counting a vocabulary reached by two channels once
    And an input of any open type is flagged and contributes nothing

  Scenario: quality reports the build-time defect proxies per process
    Given the mutation and escaped-defect counts and the process count
    When quality divides them
    Then it reports the non-equivalent mutation density and the escaped-defect density per process, labelled a proxy

  Scenario: cost projects a dollar band from breadth and depth, priced by work class
    Given a size in CFP, a case count, a work class, and a priced, dated rate model
    When cost sums the CFP times the per-CFP rates and the case count times the per-case rate, both read under the work class
    Then it reports the compute, oversight, tooling, case, and total dollars with the price date, basis, and work class
    And with no model, or a work class the model does not price, it produces no figure and is marked uncalibrated, fabricating no constant

  Scenario: duration projects a wall-clock band from an injected rate model
    Given a size in CFP and a rate model's throughput
    When duration divides size by the fast and slow throughputs
    Then it reports the low and high day band, or is marked uncalibrated with no model

  Scenario: jones reports the measured ratio to the benchmark per construct
    Given the native actuals and Jones's benchmark constants
    When jones divides native by benchmark
    Then it reports the backfiring, cost-per-FP, defect-potential, and schedule ratios
    And with either side absent it is marked uncalibrated, fabricating no benchmark value

  Scenario: estimate assembles the full artifact for one module
    Given a source, a rate model, Jones constants, and the build inputs
    When estimate composes the dimensions
    Then it returns the size, cost, duration, quality, jones, integrity, and assumptions, wrapped in a result
    And every un-supplied input is recorded as uncalibrated, and a malformed source returns the size fault
