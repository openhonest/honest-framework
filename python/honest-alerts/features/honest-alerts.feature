Feature: honest-alerts (Python) — the termination and acknowledgment dispatch tables

  These scenarios cover the host-specific decomposition: is_terminated selects a predicate by the
  message's termination condition, and an acknowledged message selects a predicate by its ack_scope.
  The public contract lives in specs/features/honest-alerts.feature; these are the Python dispatch
  entries that implement it.

  Scenario: _terminated_ttl ends a message after its time to live
    Given a ttl message and a current time
    When _terminated_ttl checks it
    Then the message has ended once the current time passes sent_at plus ttl_seconds, the edge inclusive

  Scenario: _terminated_acknowledged ends a message when its scope is satisfied
    Given an acknowledged-condition message and the acknowledgment events for it
    When _terminated_acknowledged checks it
    Then the message has ended when the message's ack_scope predicate is satisfied

  Scenario: _terminated_event ends a message on a matching terminating event
    Given an event-condition message and the event log
    When _terminated_event checks it
    Then the message has ended when a matching event is appended at or after the message was sent

  Scenario: _terminated_never keeps a message live forever
    Given a never-condition message
    When _terminated_never checks it
    Then the message is never terminated by condition

  Scenario: _acknowledged_session ends on this session's acknowledgment
    Given the acknowledgments for a session-scope message and the querying actor
    When _acknowledged_session checks them
    Then the message has ended when this DOM session has an acknowledgment

  Scenario: _acknowledged_actor ends on the actor's acknowledgment
    Given the acknowledgments for an actor-scope message and the querying actor
    When _acknowledged_actor checks them
    Then the message has ended when the recipient actor has acknowledged on any session

  Scenario: _acknowledged_broadcast ends on any recipient's acknowledgment
    Given the acknowledgments for a broadcast-scope message
    When _acknowledged_broadcast checks them
    Then the message has ended when any one recipient has acknowledged

  Scenario: _event_filter_matches tests an optional terminating-event filter
    Given a terminating event and an optional filter
    When _event_filter_matches checks them
    Then a null filter matches unconditionally, otherwise every filter key must equal the event payload's value

  Scenario: _render_card renders a card surface
    Given a message with a card dom_surface
    When _render_card renders it
    Then it returns a surface-classed div with the subject, an optional body, and a reply button per option

  Scenario: _render_badge renders a badge surface
    Given a message with the badge dom_surface
    When _render_badge renders it
    Then it returns a badge element carrying the message id and subject with a count of one
