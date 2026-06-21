Feature: honest-observe — event envelope, recording, and projection
  One scenario per function. honest-test's auto-generation proves every case;
  each scenario names the single behaviour that proof stands on, and the count of
  scenarios is the module's directly-counted function-point size.

  Scenario: build_event assembles a validated envelope
    Given the type, version, aggregate, payload, id, time, and sequence of an event
    When build_event assembles them
    Then it yields an event carrying every field
    But if any required field is empty it yields an "invalid_event" fault

  Scenario: extract_auth selects the configured authentication fields from a context
    Given a context and a list of authentication field names
    When extract_auth reads them
    Then it returns just those names that are present, in order
    But if none are present it returns nothing

  Scenario: extract_meta selects the configured metadata fields from a context
    Given a context and a list of metadata field names
    When extract_meta reads them
    Then it returns just those names that are present
    But if none are present it returns nothing

  Scenario: emit records one event
    Given an event to record and somewhere to append it
    When emit records the event
    Then it appends a complete envelope and returns the recorded event's id
    But if a required field is empty it returns the validation fault and appends nothing
    And if appending fails it returns an "emit_failed" fault

  Scenario: apply_projection folds the matching events into a view
    Given a list of events, a fold, a starting view, and optional filters
    When apply_projection runs
    Then it folds only the events that pass the filters into the view

  Scenario: matches decides whether an event passes a projection's filters
    Given an event and filters for type, aggregate, and a time window
    When matches checks it
    Then it passes only when every filter that is set is satisfied
    And the time window includes its start and excludes its end
