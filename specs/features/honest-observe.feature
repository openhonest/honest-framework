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

  Scenario: chain_started builds the chain-started event
    Given a chain name, link count, and input types
    When chain_started builds the event
    Then it returns the hf.chain.started event for the chain with its link count and input types

  Scenario: chain_completed builds the chain-completed event
    Given a chain name, link count, duration, and result
    When chain_completed builds the event
    Then it returns the hf.chain.completed event, carrying the fault code and category only when the chain finished in error

  Scenario: link_executed builds the link-executed event
    Given a link's name, chain, duration, result, boundary flag, and honesty measurements
    When link_executed builds the event
    Then it returns the hf.link.executed event with the mutation, singleton, nondeterminism, and io-call measurements, and the fault code only on error

  Scenario: link_faulted builds the link-faulted event
    Given a link's name, chain, fault code, category, and message
    When link_faulted builds the event
    Then it returns the hf.link.faulted event, including the input manifest only when supplied

  Scenario: classify_completed builds the classification event
    Given a vocabulary name, token and rejection counts, duration, and reason histogram
    When classify_completed builds the event
    Then it returns the hf.classify.completed event for the vocabulary with its counts and rejection reasons

  Scenario: state_transitioned builds the state-transition event
    Given a machine, entity, from and to states, event, and duration
    When state_transitioned builds the event
    Then it returns the hf.state.transitioned event keyed by machine and entity with the transition

  Scenario: state_rejected builds the state-rejection event
    Given a machine, entity, current state, event, and fault code
    When state_rejected builds the event
    Then it returns the hf.state.rejected event keyed by machine and entity with the fault code
