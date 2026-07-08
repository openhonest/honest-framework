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

  Scenario: link_summary builds one link's entry for a canonical request
    Given a link's name, duration, and result
    When link_summary builds the entry
    Then it returns the link summary, including the fault code only on error

  Scenario: request_canonical builds the canonical request event
    Given the HTTP, identity, chain, classification, persistence, outcome, and timing facts of a request
    When request_canonical builds the event
    Then it returns the hf.request.canonical event keyed by request id, with source server and the optional identity, chain, and fault fields present only when supplied

  Scenario: app_started builds the application-started event
    Given an app name, environment, and loaded counts
    When app_started builds the event
    Then it returns the hf.app.started event for the app, including the release only when supplied

  Scenario: app_stopped builds the application-stopped event
    Given an app name, uptime, and reason
    When app_stopped builds the event
    Then it returns the hf.app.stopped event with the uptime and reason

  Scenario: app_error builds the application-error event
    Given an app name, error type, and message
    When app_error builds the event
    Then it returns the hf.app.error event, including the traceback and context only when supplied

  Scenario: event_log_schema is the honest_event_log persist table
    Given the event envelope shape
    When event_log_schema builds the table
    Then it returns a one-table persist schema whose columns mirror the envelope, with event_id the primary key, the framework fields NOT NULL, the auth and meta partitions nullable, and the four projection indexes

  Scenario: event_log_manifest declares the table append-only
    Given the event-log table
    When event_log_manifest wraps it
    Then it returns the honest_event_log manifest with append_only true and the embedded schema

  Scenario: build_snapshot records a projection's state at a log position
    Given a projection id, a log position, and the folded state
    When build_snapshot records them
    Then it returns a snapshot with the projection id, the position it covers, and the state

  Scenario: should_snapshot fires only when the interval is reached
    Given an event count since the last snapshot and a snapshot interval
    When should_snapshot decides
    Then it is true once the count reaches a positive interval, and never when there is no interval

  Scenario: declare_projection bundles the projection config and fold
    Given a projection id, filters, fold, initial state, and snapshot interval
    When declare_projection bundles them
    Then it returns a declaration carrying the id, fold, and interval, with the aggregate filters present only when set

  Scenario: resume_from_snapshot replays only the events after the snapshot
    Given a snapshot and the events around its position
    When resume_from_snapshot replays from it
    Then it folds only the strictly-later matching events onto the snapshot state, leaving the position's own event already counted

  Scenario: otel_signal_kind maps an hf event to its OTel signal kind
    Given an hf framework event type
    When otel_signal_kind maps it
    Then it returns the OTel signal kind for a framework event and None for any other

  Scenario: _auth_attrs maps an event's auth partition to hf.auth attributes
    Given an event's auth partition
    When _auth_attrs reads it
    Then it returns the caller, data owner, and factors-presented as hf.auth attributes, each only when its field is present

  Scenario: otel_attributes derives the OTel semantic-convention attributes
    Given an hf event with a payload, optional auth partition, and optional meta release
    When otel_attributes derives them
    Then it returns the hf attributes its event type contributes, the hf.auth attributes from its auth partition, and service version from meta release, and nothing for an event with no attribute builder

  Scenario: otel_signal is the projection output for one event
    Given an hf event
    When otel_signal projects it
    Then it returns the event type, OTel signal kind, and attributes as one signal

  Scenario: _chain_started_attrs builds the chain-started span attributes
    Given a chain-started payload
    When _chain_started_attrs reads it
    Then it returns the hf chain name and link count

  Scenario: _chain_completed_attrs builds the chain-completed span attributes
    Given a chain-completed payload
    When _chain_completed_attrs reads it
    Then it returns the hf chain name and link count, with the fault code only when the chain errored

  Scenario: _link_executed_attrs builds the link span attributes
    Given a link-executed payload
    When _link_executed_attrs reads it
    Then it returns the hf link name, boundary flag, and the mutation, singleton, nondeterminism, and io-call measurements

  Scenario: _link_faulted_attrs builds the faulted-link span attributes
    Given a link-faulted payload
    When _link_faulted_attrs reads it
    Then it returns the hf link name

  Scenario: _classify_attrs builds the classification metric attributes
    Given a classify-completed payload
    When _classify_attrs reads it
    Then it returns the hf vocabulary name and rejection count

  Scenario: _state_attrs builds the state-transition span-event attributes
    Given a state-transitioned payload
    When _state_attrs reads it
    Then it returns the hf state machine, from state, event, and to state

  Scenario: build_browser_event assembles a validated browser envelope
    Given a browser event type, version, timestamp, session, payload, and event id
    When build_browser_event assembles them
    Then it returns an ok browser event with source browser and the request id only when supplied, or an invalid_event fault naming any empty required field

  Scenario: browser_classify builds the attribute-classification event payload
    Given an element, attribute, tokens, manifest, and duration
    When browser_classify builds the payload
    Then it returns the hf.browser.classify event with the request id only within a request context

  Scenario: browser_request builds the HTMX-request event payload
    Given an HTMX method, url, trigger, target, manifest keys, and request id
    When browser_request builds the payload
    Then it returns the hf.browser.request event carrying the request id it sent

  Scenario: browser_response builds the HTMX-response event payload
    Given a request id, status, swap target, and round-trip duration
    When browser_response builds the payload
    Then it returns the hf.browser.response event joined to its request by request id

  Scenario: dom_changed builds the manifest-state-change event payload
    Given the changed keys with their previous and new values
    When dom_changed builds the payload
    Then it returns the hf.dom.changed event with the request id only within a request context

  Scenario: format_tail_line renders one event as a structured tail line
    Given a logged event
    When format_tail_line renders it
    Then it returns the clock time, source defaulting to server, event type, and the event-type-specific field tail

  Scenario: _ms renders a nanosecond duration in milliseconds
    Given a duration in nanoseconds
    When _ms renders it
    Then it returns the millisecond display string to one decimal place

  Scenario: _short_time takes the clock portion of a timestamp
    Given an ISO timestamp
    When _short_time takes its clock portion
    Then it returns the time to millisecond precision

  Scenario: _tail_fields renders the field tail for an event type
    Given an event with a mapped or unmapped type
    When _tail_fields renders it
    Then it returns the event-type-specific key=value fields, or empty for an unmapped type

  Scenario: format_inspect reconstructs a request's execution trace
    Given a request id and the request's correlated events
    When format_inspect reconstructs the trace
    Then it returns the header, the browser and server blocks ordered by timestamp, and the single-clock timing breakdown

  Scenario: _request_id_of finds the request id wherever it is present
    Given an event that may carry a request id in its envelope, payload, or aggregate id
    When _request_id_of reads it
    Then it returns the request id where present, and None where none is

  Scenario: _browser_line renders one browser event for the trace
    Given a browser event
    When _browser_line renders it
    Then it returns the clock time, abbreviated event type, and the event detail

  Scenario: _server_lines renders the server section from the canonical link sequence
    Given a canonical event payload with its link sequence
    When _server_lines renders the section
    Then it returns one line per link with name, result, duration, and the fault code on an errored link

  Scenario: _inspect_breakdown attributes the elapsed time across the tiers
    Given a canonical payload and the browser events
    When _inspect_breakdown attributes the time
    Then it returns server from the canonical duration, network from the round trip minus server, browser from the browser-local durations, and their sum

  Scenario: _whole_ms renders a millisecond quantity as whole milliseconds
    Given a millisecond quantity
    When _whole_ms renders it
    Then it returns the rounded whole-millisecond display string

  Scenario: run_named_projection resolves and runs a projection by name
    Given a projection registry, a name, and the events
    When run_named_projection runs it
    Then it returns ok of the folded state for a known name, or an unknown_projection fault for one not registered

  Scenario: custom_metric declares a metric as a fold and a value over the log
    Given a name, event types, fold, value, and initial state
    When custom_metric declares the metric
    Then it returns a declaration carrying the events it folds, the fold, the value, and the initial state

  Scenario: compute_metric computes a metric's current value over the log
    Given a metric and the events
    When compute_metric runs it
    Then it folds the metric's events from the initial state and extracts the value

  Scenario: condition_met decides whether a value crosses a threshold
    Given a metric value and a condition operator and bound
    When condition_met decides
    Then it returns whether the value crosses the bound under the operator

  Scenario: builtin_metrics provides the ready-made threshold metrics by name
    Given the framework's own events
    When builtin_metrics is asked for the metrics
    Then it returns the self-contained built-in metrics over observe's events, each a fold and a value

  Scenario: _percentile takes the nearest-rank percentile of a list
    Given a list of numbers and a percentile
    When _percentile takes it
    Then it returns the nearest-rank value, and zero for no values

  Scenario: threshold_projection declares what to watch and the line to cross
    Given a metric name, condition, window, cooldown, alert, and optional remediation
    When threshold_projection declares it
    Then it returns the declaration carrying them, with the remediation present only when supplied

  Scenario: evaluate_threshold decides whether a threshold fires now
    Given a threshold projection, its metric, and the events
    When evaluate_threshold decides
    Then an enabled projection fires with its value when the condition is crossed, and a disabled one never fires

  Scenario: rejection records a raw event that failed translation
    Given a source, reason, raw event, translator version, rejection id, and received-at time
    When rejection records them
    Then it returns the rejection record preserving the raw event verbatim with its source and reason

  Scenario: rejection_log_schema is the honest_rejection_log persist table
    Given the rejection record shape
    When rejection_log_schema builds the table
    Then it returns a one-table persist schema with rejection_id the primary key and forensic indexes by source, reason, and time

  Scenario: rejection_log_manifest declares the table append-only
    Given the rejection-log table
    When rejection_log_manifest wraps it
    Then it returns the honest_rejection_log manifest with append_only true and the embedded schema

  Scenario: hlc_send advances a hybrid logical clock on a local event
    Given a local clock and the wall-clock physical time
    When hlc_send advances it
    Then it takes the later physical time, resetting the logical counter when the clock advanced and incrementing it otherwise

  Scenario: hlc_receive merges an incoming clock into the local one
    Given a local clock, an incoming clock, and the wall-clock time
    When hlc_receive merges them
    Then the new physical time is the max of the three, the logical counter follows whichever the max came from, and the source stays local

  Scenario: hlc_compare gives the total order on hybrid logical clocks
    Given two hybrid logical clocks
    When hlc_compare orders them
    Then it compares by physical time, then logical counter, then source identifier

  Scenario: identity_claimed records a mapping from an external id to a canonical id
    Given a canonical id, external system, external id, evidence, and who asserted it
    When identity_claimed records the claim
    Then it returns the identity.claimed event carrying the mapping and its evidence

  Scenario: identity_unknown records an unresolvable external id
    Given an external id and its source
    When identity_unknown records it
    Then it returns the identity.unknown event for the id and source

  Scenario: fold_identity_claims projects claims into a binding lookup
    Given a log of identity claims
    When fold_identity_claims projects them
    Then it returns the bindings keyed by system and external id, with a differing claim recorded as a conflict rather than overwriting

  Scenario: resolve_identity maps an external id to its canonical id
    Given an external id, its source, and the bindings
    When resolve_identity looks it up
    Then it returns the canonical id where bound, and None for an unknown source or id
