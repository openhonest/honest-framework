Feature: honest-errors — one report, environment-keyed policy, a pure throttle
  One scenario per function, private helpers included, so the scenario count is the
  module's directly-counted function-point size. No I/O anywhere in the module.

  Scenario: classify_js_payload normalizes a browser error into one report
    Given a browser error payload, an environment, and a timestamp
    When classify_js_payload normalizes it
    Then it returns a report carrying the payload's message, source, and line
    But if a required field is missing it returns a "malformed_payload" fault

  Scenario: classify_py_payload normalizes a server exception into one report
    Given a server exception payload, an environment, and a timestamp
    When classify_py_payload normalizes it
    Then it returns a report whose severity defaults to "error"
    But if a required field is missing it returns a "malformed_payload" fault

  Scenario: should_bypass_dedup never silences a critical failure
    Given a severity
    When should_bypass_dedup checks it
    Then it answers yes only when the severity is critical

  Scenario: _js_severity derives a browser report's severity from its message
    Given a browser payload
    When _js_severity reads its message
    Then it is critical when the message is marked critical, otherwise error

  Scenario: _missing lists the required keys a payload lacks
    Given a payload and a list of required keys
    When _missing checks them
    Then it returns the required keys that are absent, in order

  Scenario: behaviors_for looks up the behaviors for an environment
    Given an environment
    When behaviors_for looks it up
    Then it returns that environment's ordered behaviors
    But an unknown environment falls back to the development behaviors

  Scenario: dedup_key identifies a report for throttling
    Given a report
    When dedup_key reads it
    Then it returns the report's type, file, and line

  Scenario: _key_str renders a dedup key as one string
    Given a dedup key
    When _key_str renders it
    Then it returns one stable string of the type, file, and line

  Scenario: new_state starts an empty throttle state
    When new_state is called
    Then it returns a state with no recent sends and no dedup entries

  Scenario: check_rate_limit decides whether to send and threads new state forward
    Given a key, a config, a prior state, and the current time
    When check_rate_limit decides
    Then it allows the send and records it when within the limits
    But it suppresses with "rate_limit_hourly" when the hourly cap is reached
    And it suppresses with "rate_limit_dedup" when the same key fired within the window
    And it never changes the state it was given

  Scenario: format_email_body renders a report as plain text
    Given a report
    When format_email_body renders it
    Then it returns plain text with the severity, location, message, and traceback
