Feature: sample arithmetic
  A conformance fixture for the I/O boundary: its steps are registered by _sample_steps.py.

  Scenario: adding two numbers
    Given the number 2
    And the number 3
    Then the running total is 5
