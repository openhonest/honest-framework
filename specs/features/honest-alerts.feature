Feature: honest-alerts — messages between actors, mailboxes as projections over the event log

  Scenario: validate_actor_ref checks that a reference names a declared actor type
    Given an actor reference
    When validate_actor_ref checks it
    Then a reference whose type is not a declared actor type is a client fault, and id and tenant are optional

  Scenario: validate_termination checks a termination spec's condition and required fields
    Given a termination spec
    When validate_termination checks it
    Then an undeclared condition, or a declared condition missing its required fields, is a client fault

  Scenario: validate_reply_option checks a reply option's required fields and style
    Given a reply option
    When validate_reply_option checks it
    Then a missing option_id or label_id, or an undeclared style, is a client fault

  Scenario: validate_message checks the envelope and every sub-schema
    Given a message envelope
    When validate_message checks it
    Then a missing required field, an invalid actor reference, termination, ack scope, DOM surface, or reply option is a client fault

  Scenario: validate_channel_config checks a channel config's channel and recipient
    Given a channel config
    When validate_channel_config checks it
    Then a missing channel, an undeclared channel, or an invalid recipient reference is a client fault

  Scenario: validate_escalation_rule checks an escalation rule's fields and channel
    Given an escalation rule
    When validate_escalation_rule checks it
    Then a missing ttl_seconds or escalate_to, an invalid escalate_to reference, or an undeclared escalate_channel is a client fault

  Scenario: validate_alert_route checks a route and every channel config and escalation
    Given an alert route
    When validate_alert_route checks it
    Then a missing required field, an undeclared sender type, or an invalid channel config or escalation is a client fault

  Scenario: message_type_matches matches a route pattern against a message type
    Given a route's message_type pattern and a message type
    When message_type_matches compares them
    Then a pattern ending in .* matches any type in that namespace, otherwise the match is exact

  Scenario: matching_routes selects and orders the routes that handle a message
    Given the routing table and a message
    When matching_routes filters and orders it
    Then it returns the routes whose type and sender match, priority ascending, dropping the rest

  Scenario: delivery_plan builds one pending delivery per channel
    Given a message, the matched routes, and the current time
    When delivery_plan is built
    Then it returns a pending record per channel, with the resolved recipient and deliver_at of now plus the delay

  Scenario: supervise routes a message into deliveries and events
    Given a message, the routing table, and a runtime
    When supervise runs
    Then it writes a delivery per channel and emits alert.sent, or emits alert.no_route and delivers nothing

  Scenario: execute_deliveries dispatches due deliveries and records the outcome
    Given a runtime with due pending deliveries
    When execute_deliveries runs
    Then each delivery is dispatched and marked delivered or failed, emitting the matching event

  Scenario: advance applies a lifecycle event and names the event it produces
    Given a message's current lifecycle state and an event
    When advance applies it to the lifecycle state machine
    Then a valid transition returns the next state and the honest-observe event it produces, otherwise a fault

  Scenario: build_message assembles the envelope from the send arguments
    Given the send arguments, a request context, and an injected id and time
    When build_message assembles the envelope
    Then it fills the message from opts and defaults, taking the sender from opts, then the context actor, then the framework

  Scenario: send_message validates and routes a built message
    Given a built message and a runtime
    When send_message runs
    Then a valid message is routed through the supervisor and its id and delivery count reported, otherwise the validation fault is returned

  Scenario: send builds and dispatches a message fire and forget
    Given the send arguments and a runtime
    When send runs
    Then it builds the envelope with the runtime's id and time and dispatches it

  Scenario: send_and_wait dispatches and awaits a reply
    Given the send arguments and a runtime
    When send_and_wait runs
    Then the message is marked reply_required with a resume token, and it returns the reply, a timeout, or the validation fault

  Scenario: render_surface renders a message as its declared DOM surface
    Given a message with a declared dom_surface
    When render_surface renders it
    Then it returns the server-rendered HTMX fragment for that surface, with the subject, any body, and a reply button per option

  Scenario: handle_reply records the reply and returns the empty fragment
    Given a reply to a message and a runtime
    When handle_reply runs
    Then it emits alert.replied then alert.acknowledged and returns the empty fragment that removes the surface

  Scenario: recipient_matches resolves whether a message addresses an actor
    Given a message recipient and an actor
    When recipient_matches compares them
    Then the types must match, a null recipient id broadcasts to all of that type, and a set id or tenant must equal the actor's

  Scenario: is_terminated decides whether a message has ended for an actor
    Given an alert.sent event and the event log at a point in time
    When is_terminated evaluates the message's termination condition
    Then the message has ended exactly when its declared condition, one of ttl, acknowledged, event, or never, is met

  Scenario: mailbox projects an actor's pending messages
    Given the event log and an actor at a point in time
    When mailbox projects the log
    Then it returns the alert.sent messages addressed to the actor and not yet terminated, oldest first
