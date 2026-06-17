Feature: honest-gherkin smoke test
  The runner can parse a feature, match its steps, run them, and report.
  This file is the self-test that proves the loop works end-to-end.

Scenario: double a number
  Given the number 3
  When I double it
  Then the result is 6

Scenario: halve a number
  Given the number 10
  When I halve it
  Then the result is 5
