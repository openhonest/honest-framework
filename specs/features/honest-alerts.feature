Feature: honest-alerts — messages between actors, mailboxes as projections over the event log

  One scenario per function in honest-alerts.hd, no orphans: the pure core, the readers that pull
  from the clock, randomness, honest-persist and honest-observe, the output boundaries that write
  the queue, the log and the channels, the orchestrators that run one path each, and the doors the
  world calls. The Python decomposition of the dispatch tables lives in the module's own feature
  file; these are the architecture's functions.

  # --- Pure core ---------------------------------------------------------------

  Scenario: build_message assembles the envelope from the send arguments
    Given the send arguments, an injected message id, and a send time
    When build_message assembles the envelope
    Then it returns a complete message with the sender, recipient, defaults, and surface fields

  Scenario: validate_message checks the envelope and every sub-schema
    Given a message envelope
    When validate_message checks it
    Then it returns the message, or the first client fault from a missing field, a bad actor reference, a bad termination, a bad ack scope, a bad channel or surface, or a bad reply option

  Scenario: validate_actor_ref checks that a reference names a declared actor type
    Given an actor reference
    When validate_actor_ref checks it
    Then it returns the reference, or a client fault when the type is not a declared actor type

  Scenario: validate_termination checks a termination spec's condition and required fields
    Given a termination spec
    When validate_termination checks it
    Then it returns the spec, or a client fault for an undeclared condition or a missing required field

  Scenario: validate_reply_option checks a reply option's required fields and style
    Given a reply option
    When validate_reply_option checks it
    Then it returns the option, or a client fault for a missing field or an undeclared reply style

  Scenario: validate_channel_config checks a channel config's channel and recipient
    Given a channel config
    When validate_channel_config checks it
    Then it returns the config, or a client fault for a missing field or an undeclared channel

  Scenario: validate_escalation_rule checks an escalation rule's fields and channel
    Given an escalation rule
    When validate_escalation_rule checks it
    Then it returns the rule, or a client fault for a missing field or an undeclared escalation channel

  Scenario: validate_alert_route checks a route and every channel config and escalation
    Given an alert route
    When validate_alert_route checks it
    Then it returns the route, or the first client fault from a missing field, a bad sender type, a bad channel config, or a bad escalation rule

  Scenario: advance applies a lifecycle event and names the event it produces
    Given a current lifecycle state and an event
    When advance applies the event
    Then it returns the next state and the honest-observe event it produces, or the transition fault for an undeclared or impossible event

  Scenario: message_type_matches matches a route pattern against a message type
    Given a route pattern and a message type
    When message_type_matches compares them
    Then a trailing wildcard matches the namespace, otherwise the match is exact

  Scenario: matching_routes selects and orders the routes that handle a message
    Given a routing table and a message
    When matching_routes selects the routes
    Then it returns the routes whose pattern and sender type match, ordered by priority

  Scenario: delivery_plan builds one pending delivery per channel
    Given a message, its matched routes, and the current time
    When delivery_plan builds the plan
    Then it returns one pending delivery record per channel with its recipient and deliver-at time

  Scenario: alert_event shapes a cataloged event for honest-observe
    Given an event type, an aggregate id, and a payload
    When alert_event shapes the event
    Then it returns the observe emit arguments, or a server fault when the event type is not cataloged

  Scenario: mailbox projects an actor's pending messages
    Given an actor reference, the event log, and a time
    When mailbox projects the actor's messages
    Then it returns the messages addressed to the actor that have not terminated, oldest first

  Scenario: is_terminated decides whether a message has ended for an actor
    Given a message's sent event, the actor, the event log, and a time
    When is_terminated checks it
    Then it selects the predicate for the message's termination condition and returns its answer

  Scenario: recipient_matches resolves whether a message addresses an actor
    Given a message recipient and a querying actor
    When recipient_matches compares them
    Then it returns whether the recipient names that actor

  Scenario: render_surface renders a message as its declared DOM surface
    Given a message with a declared dom_surface
    When render_surface renders it
    Then it selects the renderer for the surface and returns the HTML fragment

  Scenario: resolve_config merges a parsed config over the defaults
    Given a parsed configuration
    When resolve_config merges it
    Then it returns each section's defaults overlaid with the parsed values

  # --- Readers: the module pulls from the world --------------------------------

  Scenario: now reads the wall clock
    Given the wall clock
    When now reads it
    Then it returns the current time in epoch seconds

  Scenario: new_message_id draws a fresh message id
    Given the random source
    When new_message_id draws one
    Then it returns a fresh unique message id

  Scenario: new_resume_token draws a fresh reply token
    Given the random source
    When new_resume_token draws one
    Then it returns a fresh unique reply-correlation token

  Scenario: read_routes reads the routing table from honest-persist
    Given a connection to honest-persist
    When read_routes reads the table
    Then it returns the routing records

  Scenario: read_pending reads the due pending deliveries from honest-persist
    Given a connection to honest-persist
    When read_pending reads the queue
    Then it returns the pending delivery records

  Scenario: read_events reads an actor's events from honest-observe
    Given a connection to honest-observe and an actor reference
    When read_events reads the log
    Then it returns the events addressed to that actor

  Scenario: await_reply waits for a reply event from honest-observe
    Given a connection to honest-observe, a message id, and a timeout
    When await_reply waits
    Then it returns the reply when its event arrives, or absent when the timeout passes

  Scenario: read_raw_config reads the alert configuration file
    Given the configuration file
    When read_raw_config reads it
    Then it returns the parsed raw configuration

  # --- Output boundaries: the module pushes to the world -----------------------

  Scenario: write_delivery appends a delivery record to honest-persist
    Given a delivery record and a connection
    When write_delivery writes it
    Then the record is appended to the delivery queue and the result is returned

  Scenario: mark_delivery updates a delivery record's status in honest-persist
    Given a delivery record, a status, and a connection
    When mark_delivery updates it
    Then the record's status is updated and the result is returned

  Scenario: emit_event appends an alert event to honest-observe
    Given a shaped event and a connection
    When emit_event appends it
    Then the event is written to the log and the recorded event is returned

  Scenario: deliver_dom delivers a message over the DOM channel
    Given a delivery for the dom channel and a connection
    When deliver_dom delivers it
    Then the message is pushed to the DOM surface and the result is returned

  Scenario: deliver_email delivers a message over the email channel
    Given a delivery for the email channel and a connection
    When deliver_email delivers it
    Then the message is sent to the email endpoint and the result is returned

  Scenario: deliver_sms delivers a message over the SMS channel
    Given a delivery for the sms channel and a connection
    When deliver_sms delivers it
    Then the message is sent to the SMS endpoint and the result is returned

  Scenario: deliver_webhook delivers a message over the webhook channel
    Given a delivery for the webhook channel and a connection
    When deliver_webhook delivers it
    Then the message is posted to the webhook endpoint and the result is returned

  Scenario: deliver_slack delivers a message over the Slack channel
    Given a delivery for the slack channel and a connection
    When deliver_slack delivers it
    Then the message is posted to the Slack endpoint and the result is returned

  Scenario: deliver_teams delivers a message over the Teams channel
    Given a delivery for the teams channel and a connection
    When deliver_teams delivers it
    Then the message is posted to the Teams endpoint and the result is returned

  # --- Orchestrators: one per path ---------------------------------------------

  Scenario: run_send builds, validates, routes, and queues a message
    Given the send arguments and a connection
    When run_send runs the send path
    Then it builds and validates the message, reads and validates the routes, plans and writes the deliveries, and emits alert.sent, or returns the first fault

  Scenario: run_send_and_wait runs the send path and then awaits a reply
    Given the send arguments, marked reply-required, and a connection
    When run_send_and_wait runs the path
    Then it sends as run_send does and then returns the reply when it arrives, or a timeout result

  Scenario: run_deliveries dispatches each due delivery and records the outcome
    Given a connection
    When run_deliveries runs the delivery pass
    Then it reads the pending deliveries, dispatches each on its channel, advances the lifecycle, marks the record, and emits the delivered or failed event

  Scenario: record_reply records a reply and advances the lifecycle
    Given a message id, an option, a reply payload, an actor id, and a connection
    When record_reply records the reply
    Then it advances the lifecycle and emits alert.replied and alert.acknowledged

  Scenario: render_mailbox renders an actor's pending messages
    Given an actor reference, a time, and a connection
    When render_mailbox renders the mailbox
    Then it reads the actor's events, projects the pending messages, and returns their rendered surfaces

  Scenario: load_config reads and resolves the alert configuration
    Given no arguments
    When load_config loads the configuration
    Then it reads the raw configuration and returns it merged over the defaults

  # --- Doors: the world calls in -----------------------------------------------

  Scenario: send sends a message fire and forget
    Given the send arguments and a connection
    When send is called
    Then it hands the arguments to run_send and returns its result

  Scenario: send_and_wait sends a message and awaits a reply
    Given the send arguments and a connection
    When send_and_wait is called
    Then it hands the arguments to run_send_and_wait and returns its result

  Scenario: handle_reply records a reply posted from a surface
    Given a reply posted to the reply route
    When handle_reply is called
    Then it hands the reply to record_reply and returns the empty fragment that removes the surface

  Scenario: serve_mailbox serves an actor's rendered mailbox
    Given a mailbox request on the mailbox route
    When serve_mailbox is called
    Then it hands the request to render_mailbox and returns the rendered surfaces

  Scenario: tick runs one delivery pass for the worker
    Given a connection, from the delivery worker
    When tick is called
    Then it hands the connection to run_deliveries and returns its result

  Scenario: start loads the configuration at startup
    Given the configure entry
    When start is called
    Then it hands off to load_config and returns the resolved configuration
