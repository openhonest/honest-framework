Feature: honest-alerts — generated, one scenario per function (25 total)

  One scenario per declared function, the subject the function name, a bijection with the .hd.
  Derived from honest-alerts.hd alone (the function's role, signature and note).
  send_and_wait, run_send_and_wait and wait_for_reply are removed from the .hd and carry no
  scenario here.

  # hd: python/honest-alerts/honest-alerts.hd::register_message_type
  Scenario: register_message_type is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then register_message_type is listed in __all__ and resolves to a callable attribute of honest_alerts

  Scenario: register_message_type
    Given message_type: str and message_versions: list<str> and context: dict<str, any> and conn: any
    When register_message_type is called
    Then it is the message-type registration door the world calls, nothing inside the module calls it, and it hands its input to run_register_message_type and returns what that returns
    And it registers the closed set of message_version values a message_type supports, each application owning the versions for its own message types with no framework-level version set
    And it returns RegisterResult echoing the message_type and the versions now recorded on success
    And it returns a client Fault when message_versions is empty or message_type is malformed
    And it never raises; the Fault returns as a bare union arm (RegisterResult | Fault)

  # hd: python/honest-alerts/honest-alerts.hd::send
  Scenario: send is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then the literal __all__ lists exactly send, acknowledge, register_message_type, advance, mailbox, is_terminated and alert_tables_schema, in any order
    And send resolves to a callable attribute of honest_alerts
    And existing package bindings outside __all__ remain available through explicit named imports

  Scenario: send
    Given message_type: str and recipient: ActorRef and payload: dict<str, any> and opts: SendOpts and context: dict<str, any> and conn: any
    When send is called
    Then it is the primary send door, fire-and-forget with respect to the sender; the world calls it, nothing inside the module does, and it hands its input to run_send and returns what that returns
    And opts is a closed bag carrying only message_version, subject_label_id, body_label_id, channel, dom_surface, dom_target, reply_options, termination and ack_scope, never message_id, sender, sent_at, reply_required or resume_token
    And a message_version missing from opts, or outside the registered closed set for this message_type, is a client Fault; honest-alerts never defaults message_version
    And send leaves reply_required false and sets no resume_token; sender is taken from context, message_id and sent_at are generated
    And it returns SendResult carrying the count of deliveries queued on success
    And it never raises; the Fault returns as a bare union arm (SendResult | Fault), so the calling link decides whether a failed send stops its chain

  # hd: python/honest-alerts/honest-alerts.hd::acknowledge
  Scenario: acknowledge is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then acknowledge is listed in __all__ and resolves to a callable attribute of honest_alerts

  Scenario: acknowledge
    Given message_id: str and actor_ref: ActorRef and reply_payload: dict<str, any> and session: SessionId | NOTHING and acknowledged_at: int and context: dict<str, any> and conn: any
    When acknowledge is called
    Then it is the acknowledge door recording that a recipient acted on a message so the message can terminate; the world calls it, nothing inside the module does, and it hands its input to run_acknowledge and returns what that returns
    And actor_ref is pure identity carrying no session; the mailbox projection reads its id for an actor- or broadcast-scoped ack
    And session is the acking DOM session taken as an explicit parameter, carried onto the alert.acknowledged event as data so a session-scoped ack terminates the message when it equals the viewing_session a later mailbox read is taken for, NOTHING when the ack did not come in under a DOM session
    And acknowledged_at is the epoch-seconds UTC moment read at the boundary and passed in, never computed in the pure core
    And the ack event carries no scope word; the message's own ack_scope is the only scope vocabulary
    And it returns AckResult on success, or a Fault; it never raises, the Fault returning as a bare union arm (AckResult | Fault); there is no read_mailbox door because reading a mailbox is a pure projection reached by import

  Scenario: run_register_message_type
    Given message_type: str and message_versions: list<str> and context: dict<str, any> and conn: any
    When run_register_message_type is called
    Then it runs the registration path and is the single mutator of the registered-types record
    And it first reads the existing registration for message_type with read_registered_type, then hands message_type, message_versions and that existing RegisteredType-or-NOTHING to build_registered_type
    And on a build_registered_type Fault (empty version set, malformed message_type, or a refused differing re-registration) it returns the Fault without writing
    And on a RegisterDecision with action noop (the arriving whole declaration byte-identical to the stored one) it writes nothing and returns RegisterResult echoing the stored type and versions
    And on a RegisterDecision with action write (the type was never registered) it writes the decision's RegisteredType through write_registered_type, then returns RegisterResult echoing the type and versions now recorded
    And on a failed write it returns a Fault built via alerts_fault
    And no pure function mutates; it owns the one record and returns RegisterResult | Fault so any failure bubbles to the door by return

  # hd: python/honest-alerts/honest-alerts.hd::run_register_message_type
  # spec: Honest Alerts §§3b.1 and 6b (as cited by the declaration)
  Scenario: run_register_message_type returns an actionable fault when the store write fails
    Given message_type: str and message_versions: list<str> describe a valid first registration, context: dict<str, any> is the current manifest, and conn: any is a real database connection whose registered-types store refuses the write
    When run_register_message_type is called
    Then it returns a bare registration_write_failed Fault with category server and no registration is recorded
    And the message explains the failed registration write and gives the caller a meaningful next action

  Scenario: run_send
    Given message_type: str and recipient: ActorRef and payload: dict<str, any> and opts: SendOpts and context: dict<str, any> and conn: any
    When run_send is called
    Then it runs the send path and is the single mutator of the message and the delivery records
    And it pulls the fresh id with new_message_id and the clock with now, reads the registered-types record with read_registered_type, extracts the controlled fields from opts, and hands them with message_type, recipient, payload, the sender (from context) and that RegisteredType to build_message, which assembles and validates one immutable Message
    And a message_type that was never registered (read_registered_type answers NOTHING), a message_version outside the registered closed set for its type, or a malformed termination comes back from build_message as a client Fault, which it returns without writing
    And it pulls the matching routes with read_routes and hands the message and routes to supervise, the pure core that returns a DeliveryPlan
    And it writes each Delivery in the plan through write_delivery and emits alert.sent through the emit seam with the Message as payload and the message_id as aggregate_id
    And the delivery rows and the alert.sent append commit together or roll back together on one conn inside one transaction, because alert.sent is the read-path source of truth for the mailbox and must share the fate of the delivery rows
    And a rolled-back transaction is returned as a Fault; under the declared fallback it writes the delivery rows first then appends alert.sent, never emit-first, and a failed append after the rows are written is never swallowed but returned as a surfaced Fault
    And it returns SendResult carrying the count written, or a Fault built via alerts_fault, as a bare union arm (SendResult | Fault) so any failure bubbles to the door by return

  # hd: python/honest-alerts/honest-alerts.hd::run_send
  # spec: Honest Alerts §§6.1 and 6b (as cited by the declaration)
  Scenario: run_send returns an actionable fault when the event append rolls back
    Given message_type: str, recipient: ActorRef, payload: dict<str, any>, opts: SendOpts and context: dict<str, any> describe a valid send with a matching route
    And conn: any is a real database connection where delivery rows can be written but the alert.sent append fails
    When run_send is called
    Then it returns a bare append_failed Fault with category server and no delivery rows from the send are committed
    And the message explains that the event append failed and the send was rolled back, and gives the caller a meaningful next action
    And detail.message_id carries the generated message ID for the failed send

  # hd: python/honest-alerts/honest-alerts.hd::run_acknowledge
  Scenario: run_acknowledge
    Given message_id: str and actor_ref: ActorRef and reply_payload: dict<str, any> and session: SessionId | NOTHING and acknowledged_at: int and context: dict<str, any> and conn: any
    When run_acknowledge is called
    Then it runs the acknowledge path and is the single mutator of the acknowledgment event
    And it hands message_id, actor_ref, reply_payload, session and acknowledged_at to build_ack_event, the pure function that assembles the alert.acknowledged payload
    And it emits alert.acknowledged through the emit seam with the message_id as aggregate_id, so the event folds under the same aggregate as alert.sent and feeds the mailbox projection that terminates the message
    And it returns AckResult on a clean emit, or a Fault built via alerts_fault on a failed one, as a bare union arm (AckResult | Fault) so a failed acknowledge bubbles to the door by return
    And on a failed append it returns ack_append_failed with category server, detail.message_id equal to the supplied message ID and detail.observe equal to the underlying append fault code

  Scenario: build_registered_type
    Given message_type: str and message_versions: list<str> and existing: RegisteredType | NOTHING
    When build_registered_type is called
    Then it assembles and validates one registration from its parts, applies the re-registration rule against what is already stored, and returns a RegisterDecision or a Fault, pure, no world
    And an empty message_versions set, or a malformed (non-dot-namespaced or empty) message_type, returns a client Fault via alerts_fault before any re-registration comparison
    And when existing is NOTHING the type was never registered, so it returns a RegisterDecision with action write carrying the arriving record
    And when existing is a stored record and the arriving whole declaration (message_type and its message_versions set taken whole) is byte-identical to it, re-registration changes nothing, so it returns a RegisterDecision with action noop carrying the stored record
    And when existing is a stored record and the arriving declaration differs from it in any way, it refuses, returning a client Fault via alerts_fault whose detail names the existing declaration against the arriving one (both message_type values and both message_versions sets) and whose message says to change the arriving declaration to match the stored one or remove the existing registration first
    And the refusal is wrong in itself and never retryable; sending the same differing declaration again fails the same way

  # hd: python/honest-alerts/honest-alerts.hd::_is_dotted
  # spec: Honest Alerts §3b.1 (as cited by the declaration)
  Scenario: _is_dotted accepts only dotted names with nonempty components
    Given message_type: any is "approval.requested", "a.b.c", "A-1.b_2", "", "approval", ".", ".requested", "approval.", "approval..requested", or the number 7
    When _is_dotted is called
    Then it returns true for the first three strings and false for every other supplied value

  # hd: python/honest-alerts/honest-alerts.hd::build_registered_type
  Scenario: build_registered_type rejects malformed registration with a corrective message
    Given message_type: str is "", "approval", ".", ".requested", "approval." or "approval..requested" with a nonempty message_versions: list<str>, or is "approval.requested" with an empty message_versions list
    And existing: RegisteredType | NOTHING is the current registration or NOTHING
    When build_registered_type is called
    Then it returns an invalid_registration client Fault whose message explains the missing namespace or version set and directs the caller to supply a dot-namespaced type and at least one version
    And detail.message_type and detail.message_versions carry the supplied values

  # hd: python/honest-alerts/honest-alerts.hd::build_registered_type
  Scenario: build_registered_type explains a conflicting registration and its remedies
    Given message_type: str is a registered type, message_versions: list<str> differs from its stored set, and existing: RegisteredType | NOTHING contains the stored declaration
    When build_registered_type is called
    Then it returns a refused_registration client Fault with the full stored record in detail.existing and the full supplied record in detail.arriving
    And the message explains the conflict and advises matching the stored declaration or removing it before registering the new one

  Scenario: build_message
    Given message_type: str and recipient: ActorRef and payload: dict<str, any> and opts: SendOpts and sender: ActorRef and message_id: str and sent_at: int and reply_required: bool and registered: RegisteredType | NOTHING
    When build_message is called
    Then it assembles one immutable Message from its already-computed parts and validates it, returning the Message or a Fault, a pure constructor that reads no clock, random source or database
    And the impure parts message_id (from new_message_id) and sent_at (from now), the sender (from context) and reply_required (false for send, true for send_and_wait) are passed in
    And it reads the controlled fields out of opts (message_version, subject_label_id, body_label_id, channel, dom_surface, dom_target, reply_options, termination, ack_scope) and places each into the Message
    And a registered of NOTHING (the message_type was never registered), or a message_version that is not a member of registered.message_versions, returns a client Fault via alerts_fault
    And a termination whose fields do not match its condition returns a client Fault via alerts_fault
    And it never raises and never substitutes a default message_version; the only authority for which versions exist is the registered record

  # hd: python/honest-alerts/honest-alerts.hd::build_message
  # spec: Honest Alerts §§3.3 and 6b (as cited by the declaration)
  Scenario: build_message rejects an irrelevant ttl for never termination
    Given message_type: str and a registered: RegisteredType containing the message_version in opts: SendOpts, with opts.termination naming never, ttl_seconds 10, and event_type and event_filter both NOTHING
    And recipient: ActorRef, payload: dict<str, any>, sender: ActorRef, message_id: str, sent_at: int and reply_required: bool are otherwise valid
    When build_message is called
    Then it returns an invalid_termination Fault with category client

  # hd: python/honest-alerts/honest-alerts.hd::build_message
  Scenario: build_message accepts each well-formed termination condition
    Given message_type: str, recipient: ActorRef, payload: dict<str, any>, sender: ActorRef, message_id: str, sent_at: int, reply_required: bool and registered: RegisteredType | NOTHING are valid for a send
    And opts: SendOpts carries a registered version and one of these terminations
      | condition    | ttl_seconds | event_type   | event_filter |
      | ttl          | 10          | NOTHING      | NOTHING      |
      | event        | NOTHING     | system.ready | NOTHING      |
      | event        | NOTHING     | system.ready | {"ok": true} |
      | acknowledged | NOTHING     | NOTHING      | NOTHING      |
      | never        | NOTHING     | NOTHING      | NOTHING      |
    When build_message is called
    Then it returns a Message preserving the supplied termination

  # hd: python/honest-alerts/honest-alerts.hd::build_message
  Scenario: build_message rejects fields outside the chosen termination condition
    Given message_type: str, recipient: ActorRef, payload: dict<str, any>, sender: ActorRef, message_id: str, sent_at: int, reply_required: bool and registered: RegisteredType | NOTHING are valid for a send
    And opts: SendOpts carries a registered version and a termination with a missing or unsupported condition, a required field omitted, or an inapplicable field populated
    When build_message is called
    Then it returns an invalid_termination client Fault whose message identifies the mismatch and gives the correction for the condition
    And for ttl the correction is to supply ttl_seconds and clear inapplicable event_type and event_filter
    And for event the correction is to supply event_type, leave ttl_seconds as NOTHING, and optionally specify event_filter
    And for acknowledged or never the correction is to clear any supplied ttl_seconds, event_type or event_filter to NOTHING
    And for a missing or unsupported condition the correction is to supply a supported TerminationSpec

  # hd: python/honest-alerts/honest-alerts.hd::build_message
  Scenario: build_message explains registration and version faults
    Given message_type: str, recipient: ActorRef, payload: dict<str, any>, opts: SendOpts, sender: ActorRef, message_id: str, sent_at: int, reply_required: bool and registered: RegisteredType | NOTHING are otherwise valid but the type is unregistered, the version is missing, or the version is outside its registered set
    When build_message is called
    Then it returns a client Fault with code unregistered_message_type, missing_message_version or message_version_not_registered, respectively
    And the message explains which case failed and directs the caller to register the type, supply a registered version or use or register an allowed version, respectively
    And each fault carries the selected type in detail.message_type
    And the version faults also carry detail.message_version, which is NOTHING when missing or the supplied value when outside the registered set

  Scenario: supervise
    Given message: Message and routing_table: list<AlertRoute>
    When supervise is called
    Then it is the pure supervisor core producing the delivery plan from a message and the routing table, stateless with no memory between invocations, writing nothing
    And it keeps the routes whose message_type matches the message's type (including trailing-wildcard match) and whose sender_type is NOTHING or equals the message sender's type, and sorts the kept routes by priority ascending
    And a route naming "order.placed" without a wildcard matches "order.placed" and does not match the different type "order.placed.extra"
    And for each route, for each ChannelConfig, it resolves the recipient (the config's recipient_spec if set, else the message recipient), computes deliver_at as the message sent_at plus the config's delay_seconds, and builds one pending Delivery; the Deliveries in route-and-channel order are the DeliveryPlan
    And in unit 1 it declares no Fault arm: the match is assumed non-empty, so there is nothing for it to fault on; the empty-match case (alert.no_route) is a later-unit concern that would add a Fault arm, not raised here
    And it returns DeliveryPlan alone, a plan out, no world

  # hd: python/honest-alerts/honest-alerts.hd::supervise
  # spec: Honest Alerts §§5.1 and 6.1 (as cited by the declaration)
  Scenario: supervise delivers immediately for an absent channel delay
    Given message: Message has sent_at 123 and routing_table: list<AlertRoute> contains one matching route and one channel whose delay_seconds is NOTHING
    When supervise is called
    Then it returns a plan with one pending delivery whose deliver_at is 123

  Scenario: build_ack_event
    Given message_id: str and actor_ref: ActorRef and reply_payload: dict<str, any> and session: SessionId | NOTHING and acknowledged_at: int
    When build_ack_event is called
    Then it assembles the AckPayload of the alert.acknowledged event from its parts, pure, no world and no fault
    And message_id is carried so the mailbox projection can match acks to their message
    And actor_ref is the acknowledging actor, pure identity whose id goes into the payload for an actor- or broadcast-scoped ack
    And reply_payload reaches the alert.acknowledged payload, for example the chosen reply option's payload
    And acknowledged_at, read at the boundary and passed in, reaches the alert.acknowledged payload; this pure function never calls now()
    And session is placed on the payload as a typed SessionId (ActorRef carrying no session), so a session-scoped ack terminates the message when this acking session equals the viewing_session a mailbox read is taken for, NOTHING when the ack did not come in under a DOM session
    And it places no scope word on the payload; the only scope vocabulary is the message's own ack_scope, on which is_terminated dispatches, not anything this payload carries

  # hd: python/honest-alerts/honest-alerts-pure.hd::advance
  Scenario: advance is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then advance is listed in __all__ and resolves to a callable attribute of honest_alerts

  Scenario: advance
    Given state: AlertState and event: AlertEvent
    When advance is called
    Then it is the pure message-lifecycle transition function: given the current AlertState and an AlertEvent it returns the next AlertState when the pair names a declared transition
    And the declared transitions are exactly: created deliver->delivered, created fail->failed, created expire->expired; delivered read->read, delivered acknowledge->acknowledged, delivered action->actioned, delivered escalate->escalated, delivered expire->expired; read acknowledge->acknowledged, read action->actioned, read escalate->escalated, read expire->expired; escalated acknowledge->acknowledged, escalated action->actioned, escalated expire->expired
    And acknowledged, actioned, expired and failed are terminal: any event from them is undeclared
    And acknowledge from acknowledged and read from created each return an invalid_transition server Fault
    And an event undeclared from the given state returns a Fault via alerts_fault with category server
    And it is pure, a state and an event in and the next state or a fault out, reached by import, consulting no exposed object

  # hd: python/honest-alerts/honest-alerts-pure.hd::mailbox
  Scenario: mailbox is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then mailbox is listed in __all__ and resolves to a callable attribute of honest_alerts

  # hd: python/honest-alerts/honest-alerts-pure.hd::advance
  Scenario: advance explains an undeclared lifecycle transition
    Given state: AlertState is acknowledged and event: AlertEvent is acknowledge, or state is created and event is read
    When advance is called
    Then it returns an invalid_transition server Fault whose message identifies the state and event and explains that only declared pairs advance the lifecycle and terminal states accept no event
    And detail.state and detail.event carry the supplied state and event

  Scenario: mailbox
    Given actor_ref: ActorRef and at_time: int and events: list<any> and viewing_session: SessionId | NOTHING
    When mailbox is called
    Then it is an actor's mailbox as a pure projection over the events handed to it: which messages addressed to this actor have not yet terminated at at_time for the viewer the read is taken for
    And it never queries honest-observe's raw log; the caller selects the event set through an honest-observe projection and passes it as events, and mailbox folds over exactly those and reads nothing else
    And viewing_session is an explicit SessionId or NOTHING, never a defaulted optional: a real DOM read passes the session the page is rendered for, a suspended send_and_wait waiter passes NOTHING (the waiter view); it is passed straight through to is_terminated unchanged and no session is read off actor_ref
    And it keeps the alert.sent events whose recipient matches actor_ref and whose sent_at is at or before at_time, invokes is_terminated for each (handing it actor_ref, at_time, events and viewing_session) to drop the terminated ones, and returns the pending Messages ordered by sent_at ascending
    And a pending message sent exactly at at_time is included and one sent later is excluded
    And when is_terminated returns an unknown_ack_scope server Fault on the no-match row of its ack_scope dispatch, that same Fault travels by return

  # hd: python/honest-alerts/honest-alerts-pure.hd::is_terminated
  Scenario: is_terminated is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then is_terminated is listed in __all__ and resolves to a callable attribute of honest_alerts

  # hd: python/honest-alerts/honest-alerts-pure.hd::is_terminated
  Scenario: is_terminated
    Given msg: Message and actor_ref: ActorRef and at_time: int and events: list<any> and viewing_session: SessionId | NOTHING
    When is_terminated is called
    Then it decides whether one message has terminated for the viewer the read is taken for at at_time, the predicate mailbox folds with, reading msg.termination and branching on its condition
    And for ttl it is active at exactly sent_at plus ttl_seconds and terminated one second after that deadline
    And for event it is terminated when an event of the spec's event_type at or after sent_at matches the optional event_filter
    And a matching event at exactly sent_at terminates it, while one before sent_at does not
    And for never it is never terminated
    And for acknowledged it selects the alert.acknowledged event slice for this message (every event whose payload.message_id equals the message's id) and dispatches on the message's ack_scope through the scope_terminated table, one row per AckScope member plus a no-match row, never an if ladder
    And a session-scoped ack terminates only when an ack's acking session equals viewing_session, and viewing_session of NOTHING (the waiter view) never matches, so a session dismissal never ends a waiter
    And an actor-scoped ack terminates for every viewer on an ack by the recipient actor; a broadcast-scoped ack terminates for every viewer on an ack by any recipient
    And an ack from a non-recipient does not terminate an actor-scoped message (no ack whose actor_id equals actor_ref.id) nor a broadcast-scoped message (the ack slice for this message is empty)
    And the no-match row is reached only if ack_scope is a value the table does not carry, a program bug not client input, so it returns a server Fault via alerts_fault (code unknown_ack_scope, category server) rather than a silent False
    And it consults no lifecycle state machine; it is pure, returning bool | Fault, the Fault travelling by return so mailbox returns list<Message> | Fault
    And an unknown_ack_scope Fault carries the declared scope alternatives in detail.accepted and the unmatched scope in detail.arrived
    And that fault message identifies the unmatched scope and every accepted scope and says that no branch matched

  # hd: python/honest-alerts/honest-alerts-pure.hd::is_terminated
  # spec: Honest Alerts §6b
  Scenario: is_terminated reports an unknown termination condition as a server fault
    Given msg: Message carries an unmatched termination condition from an invalid domain record, actor_ref: ActorRef is the mailbox actor, at_time: int and events: list<any> are supplied, and viewing_session: SessionId | NOTHING is the viewer
    When is_terminated is called
    Then it returns an unknown_termination_condition server Fault
    And detail.accepted carries the declared termination conditions and detail.arrived carries the unmatched value
    And the message identifies the unmatched condition and every accepted condition and says that no branch matched

  # hd: python/honest-alerts/honest-alerts-pure.hd::event_at_or_after
  # spec: Honest Alerts §§3.1 and 4.1; Honest Observe §2.1
  Scenario: event_at_or_after compares canonical Observe timestamps at microsecond precision
    Given timestamp: any and sent_at: int are the following UTC timestamp and epoch-second pairs
      | timestamp                   | sent_at      | matches |
      | 1970-01-01T00:00:00.999999Z | 1            | false   |
      | 1970-01-01T00:00:01.000000Z | 1            | true    |
      | 1970-01-01T00:00:01.000001Z | 1            | true    |
      | 0001-01-01T00:00:00.000000Z | -62135596800 | true    |
      | 2000-02-29T23:59:59.000000Z | 951868799    | true    |
      | 2024-04-30T12:34:55.999999Z | 1714480496   | false   |
      | 2024-04-30T12:34:56.000000Z | 1714480496   | true    |
      | 9999-12-31T23:59:59.999999Z | 253402300799 | true    |
    When event_at_or_after is called
    Then it returns the matches value for each pair

  # hd: python/honest-alerts/honest-alerts-pure.hd::event_at_or_after
  # spec: Honest Alerts §§3.1 and 4.1; Honest Observe §2.1
  Scenario: event_at_or_after accepts legacy integers and rejects unsupported timestamps
    Given sent_at: int is 0 and timestamp: any is the legacy integer -1, 0, or 1, or is true, false, NOTHING, or "not a timestamp"
    And the invalid calendar pairs are "0000-12-31T23:59:59.999999Z" with sent_at -62135596801 and "2001-02-29T23:59:59.999999Z" with sent_at 983318400
    When event_at_or_after is called
    Then it returns true only for the integer 0 and the integer 1
    And it returns false for both invalid calendar pairs

  # hd: python/honest-alerts/honest-alerts-pure.hd::is_terminated
  # spec: Honest Alerts §4.1; Honest Observe §2.1
  Scenario: is_terminated skips a malformed timestamp and matches a later Observe event
    Given msg: Message was sent at UTC epoch second 1 and ends on system.ready, actor_ref: ActorRef is the mailbox actor, at_time: int is 2, and viewing_session: SessionId | NOTHING is NOTHING
    And events: list<any> contains a system.ready event with a malformed timestamp followed by a matching Observe event whose timestamp is "1970-01-01T00:00:01.000001Z"
    When is_terminated is called
    Then it returns true for both events together and false if only the malformed event is supplied

  Scenario: terminated_session
    Given acks: list<any> and actor_ref: ActorRef and viewing_session: SessionId | NOTHING
    When terminated_session is called
    Then it is the session-scoped row of the scope_terminated dispatch, answering whether a session-scoped message has been acknowledged for the viewer the read is taken for
    And acks is the alert.acknowledged event slice for this message, already selected by is_terminated
    And actor_ref is unused by this row, present only so every row of the dispatch shares one signature
    And it is terminated only when viewing_session is not NOTHING and some ack's acking session (payload.session) equals viewing_session
    And viewing_session of NOTHING is the waiter view and equals no session, so the NOTHING case returns false and a session dismissal never ends a waiting send_and_wait
    And a session-scoped ack by one DOM session therefore terminates only for that same session; other sessions of the same actor still see it; it is pure, a boolean out, no world and no fault

  Scenario: terminated_actor
    Given acks: list<any> and actor_ref: ActorRef and viewing_session: SessionId | NOTHING
    When terminated_actor is called
    Then it is the actor-scoped row of the scope_terminated dispatch, answering whether an actor-scoped message has been acknowledged for every viewer
    And acks is the alert.acknowledged event slice for this message, already selected by is_terminated
    And actor_ref is the recipient actor whose mailbox is being computed, pure identity read for its id
    And viewing_session is ignored here; an actor-scoped ack terminates for every viewer, the waiter (viewing_session = NOTHING) included
    And it is terminated when some ack's payload.actor_id equals actor_ref.id, that is, when the recipient actor acknowledged on any one of its sessions; it is pure, a boolean out, no world and no fault

  Scenario: terminated_broadcast
    Given acks: list<any> and actor_ref: ActorRef and viewing_session: SessionId | NOTHING
    When terminated_broadcast is called
    Then it is the broadcast-scoped row of the scope_terminated dispatch, answering whether a broadcast-scoped message has been acknowledged for every viewer
    And acks is the alert.acknowledged event slice for this message, already selected by is_terminated
    And actor_ref and viewing_session are both ignored here; a broadcast-scoped ack by any one recipient terminates for every viewer, the waiter (viewing_session = NOTHING) included
    And it is terminated when the acks slice is non-empty, that is, when any recipient acknowledged; it is pure, a boolean out, no world and no fault

  Scenario: alerts_fault
    Given code: str and message: str and category: FaultCategory and detail: dict<str, any>
    When alerts_fault is called
    Then it builds one honest-alerts Fault record from its parts, the single place honest-alerts assembles a fault
    And code is the specific reason (approval_timeout, approval_rejected, or a build/send failure code); message is the human sentence naming what went wrong and what to do instead; category is who is responsible, a FaultCategory member client or server, never free text; detail is the structured context a test reads without parsing the message
    And it sets the reserved is_err tag true and returns the Fault, carried by the return as a bare union arm and recognized by is_fault, never raised and never wrapped in an ok/err envelope
    And it is pure, reading no world

  # hd: python/honest-alerts/honest-alerts.hd::new_message_id
  # spec: Honest Alerts §3.1 (as cited by the declaration)
  Scenario: new_message_id
    Given no parameters
    When new_message_id is called
    Then it returns one fresh UUID v7 with the clock reading preserved in its leading Unix-millisecond timestamp field
    And it reads the clock for the timestamp and random for the random bits
    And its 12-bit rand_a and 62-bit rand_b fields carry random data in the UUID v7 layout
    And its clock read is distinct from the message time supplied by now
    And run_send invokes it and applies its answer into the message under construction, so the id is assigned in one place
    And it is a reader, not a pure fn, because a fresh id is a read of the world: made pure it would be a hidden non-deterministic call, the leak the reader role exists to surface

  # hd: python/honest-alerts/honest-alerts-pure.hd::uuid7_from_parts
  # spec: Honest Alerts §3.1; RFC 9562 §5.7
  Scenario: uuid7_from_parts preserves the timestamp and entropy fields in canonical text
    Given unix_ms: int is 1645557742000 and random_a: int and random_b: int are the following pairs
      | random_a | random_b             |
      | 3267     | 1784793296645077391  |
      | 3266     | 1784793296645077391  |
      | 64707    | 15619851351927241103 |
    When uuid7_from_parts is called
    Then it returns "017f22e2-79b0-7cc3-98c4-dc0c0c07398f" for the first and third pairs and "017f22e2-79b0-7cc2-98c4-dc0c0c07398f" for the second pair

  Scenario: now
    Given no parameters
    When now is called
    Then it is a reader that pulls the current wall-clock time as epoch seconds UTC
    And it reads the clock and nothing else
    And run_send invokes it once and applies its answer two ways: as the message's sent_at, and, added to each channel's delay_seconds, as each delivery's deliver_at
    And it is also the input-side clock reader the boundary uses to obtain acknowledged_at before calling the acknowledge door, so the acknowledgment time is read at the boundary and handed in as a parameter, never computed in the pure core
    And it is a reader for the same reason new_message_id is: a clock read inside a pure function is the hidden-clock leak the role declaration makes visible

  Scenario: read_routes
    Given message_type: str and conn: any
    When read_routes is called
    Then it is a reader that reads the alert_routes routing table from honest-persist for the routes that could match a message type, awaited because the read is I/O
    And message_type is the message's dot-namespaced type; the read returns every AlertRoute whose message_type matches it or wildcard-matches it, which the pure supervisor then filters and sorts, so the match decision lives in the pure core, not the query
    And conn is a standard DB-API connection (PEP 249), the injected honest-persist connection, held and passed, never read by any pure function; the alerts-owned tables and the event log are reached through the same conn, and run_send writes the delivery rows then appends alert.sent on that one conn and commits once, so the rows and the append land together or not at all
    And it reads database:given, honest-alerts' own tables whose connection it is handed at run time
    And it reads the alert_routes table name and columns from the alert_tables_schema manifest rather than hardcoding them, so the routing-table read and the manifest cannot drift
    And run_send invokes it and passes the routes to supervise

  Scenario: read_registered_type
    Given message_type: str and conn: any
    When read_registered_type is called
    Then it is a reader that reads the registered-types table from honest-persist for the RegisteredType record of one message_type, awaited because the read is I/O
    And message_type is the message's dot-namespaced type; the read returns that type's RegisteredType, carrying the closed set of versions the registering application declared, or NOTHING when the type was never registered
    And conn is a standard DB-API connection (PEP 249), the injected honest-persist connection, held and passed, never read by any pure function; the alerts-owned tables and the event log are reached through the same conn, and run_send writes the delivery rows then appends alert.sent on that one conn and commits once, so the rows and the append land together or not at all
    And it reads database:given, honest-alerts' own registered-types table whose connection it is handed at run time
    And it reads the alert_registered_types table name and columns from the alert_tables_schema manifest rather than hardcoding them, so the registry read and the manifest cannot drift
    And run_send invokes it and passes the record to build_message, which validates the message's message_version against it; a NOTHING answer (unregistered type) or a version outside the set is a client fault build_message returns
    And run_register_message_type also invokes it, to read the existing registration before deciding the re-registration rule: a NOTHING answer means the message_type was never registered and the registration is a first write, and a stored record is the declaration the arriving one is compared against byte for byte

  # hd: python/honest-alerts/honest-alerts.hd::write_delivery
  Scenario: write_delivery
    Given delivery: Delivery and conn: any
    When write_delivery is called
    Then it is an output boundary that writes one pending delivery record into the alert_deliveries queue table through honest-persist, awaited because the insert is I/O
    And delivery is one Delivery the supervisor produced, status pending
    And conn is a standard DB-API connection (PEP 249), the injected honest-persist connection; the alerts-owned tables and the event log are reached through the same conn, and run_send writes the delivery rows then appends alert.sent on that one conn and commits once, so the rows and the append land together or not at all
    And it is a terminus: it does only the write and returns the declared insertion outcome; it constructs no Fault and reads nothing
    And run_send invokes it once per delivery in the plan
    And it writes database:given, honest-alerts' own alert_deliveries table, reading that table name and columns from the alert_tables_schema manifest rather than hardcoding them, so the delivery-queue write and the manifest cannot drift
    And a successful insert returns the record {ok: true}, and the writer leaves commit to the send transaction

  Scenario: write_registered_type
    Given registered_type: RegisteredType and conn: any whose driver accepts the insert
    When write_registered_type is called
    Then it is an output boundary that writes one RegisteredType record into the module-owned registered-types table through honest-persist, awaited because the insert is I/O
    And registered_type is the record run_register_message_type assembled: the dot-namespaced message_type and the closed set of versions the application declared for it
    And conn is a standard DB-API connection (PEP 249), the injected honest-persist connection; the alerts-owned tables and the event log are reached through the same conn, and run_send writes the delivery rows then appends alert.sent on that one conn and commits once, so the rows and the append land together or not at all
    And it is a terminus: it does only the write and returns the existing success outcome; it constructs no Fault and reads nothing
    And run_register_message_type invokes it once per registration
    And it writes database:given, honest-alerts' own registered-types table, reading that table name and columns from the alert_tables_schema manifest rather than hardcoding them, so the registry write and the manifest cannot drift
    And it returns a RegisteredTypeWriteOk record with ok true

  # hd: python/honest-alerts/honest-alerts.hd::write_registered_type
  # spec: Honest Alerts §§3b.1 and 10b (as cited by the declaration)
  Scenario: write_registered_type returns a refused insert reason without ending the transaction
    Given registered_type: RegisteredType is a valid registration and conn: any is a real database connection whose driver refuses the insert in the caller's open transaction
    When write_registered_type is called
    Then it returns a RegisteredTypeWriteRefused record with ok false and the reported driver reason as data
    And no registration is inserted and the writer leaves commit and rollback to the caller

  # hd: python/honest-alerts/honest-alerts.hd::emit
  Scenario: emit
    Given event_type: str and aggregate_type: str and aggregate_id: str and payload: dict<str, any> and context: dict<str, any> and event_version: str and conn: any
    When emit is called
    Then it is the emit seam into honest-observe: it calls honest-observe's frozen emit door to append one alert.* event to the event log, awaited because emit is I/O
    And its signature is honest-observe.emit's contract exactly as frozen on main, built to that contract without redefining or widening it; the return is honest-observe's own Event-or-Fault, carried out as any because honest-observe owns that type
    And event_type is the alert.* type (alert.sent on a send, alert.acknowledged on an acknowledge)
    And aggregate_type is always alert and aggregate_id is the message_id, so every event about one message folds under one aggregate
    And payload is the Message on alert.sent and the acknowledgment facts on alert.acknowledged
    And context is the current manifest, from which honest-observe extracts the auth and meta partitions, and event_version is the alert event schema version
    And conn is a standard DB-API connection (PEP 249), the injected honest-observe log connection; the alerts-owned tables and the event log are reached through the same conn, and run_send writes the delivery rows then appends alert.sent on that one conn and commits once, so the rows and the append land together or not at all
    And it is a terminus that does only the append; run_send invokes it for alert.sent and run_acknowledge for alert.acknowledged
    And an Observe Fault returned as a value is passed through unchanged
    And if the Observe append raises at the boundary, it returns an emit_seam_failed server Fault with detail.aggregate_id and detail.event_type from the attempted append and the exception text in detail.detail
    And that fault message explains that the event append failed and the event was not appended

  # hd: python/honest-alerts/honest-alerts-pure.hd::alert_tables_schema
  # spec: Honest Alerts §10b (as cited by the declaration)
  Scenario: alert_tables_schema declares the required indexes and mutable tables
    Given no parameters
    When alert_tables_schema is called
    Then it returns manifests for exactly alert_routes, alert_deliveries and alert_registered_types
    And alert_routes declares an index on message_type
    And alert_deliveries declares indexes on the ordered column pair status and deliver_at, and on message_id
    And alert_registered_types declares no secondary index
    And each table is explicitly declared mutable rather than append-only

  # hd: python/honest-alerts/honest-alerts-pure.hd::alert_tables_schema
  Scenario: alert_tables_schema is available as an honest_alerts public export
    Given the installed honest_alerts Python package
    When the host inspects the package's public exports
    Then alert_tables_schema is listed in __all__ and resolves to a callable attribute of honest_alerts

  Scenario: alert_tables_schema
    Given no parameters
    When alert_tables_schema is called
    Then it is a pure function that returns the three alerts-owned honest-persist table manifests as data: alert_routes (the routing table), alert_deliveries (the delivery queue) and alert_registered_types (the message-type registry), all living in the same honest-persist database as the honest-observe event log so run_send can write the delivery rows and append alert.sent across both inside one transaction
    And it is the honest-alerts twin of honest-observe's event_log_schema
    And each manifest names that table's columns and their types and the indexes the module's reads need: alert_routes keyed by route_id with message_type (supporting a trailing wildcard), a nullable sender_type, channels and a nullable escalation as JSON text, an integer priority, and an index on message_type; alert_deliveries keyed by delivery_id with message_id, route_id, channel, recipient as JSON text, an integer deliver_at in epoch seconds UTC, a status of pending, delivered or failed, and indexes on (status, deliver_at) and on message_id; alert_registered_types keyed by message_type with message_versions as JSON text
    And unlike the event log these tables are not append-only: alert_deliveries rows move from pending to delivered or failed and alert_registered_types accepts a byte-identical re-registration as a no-op; the manifest declares the mutable table shape honest-persist enforces
    And it is pure: it returns the manifest as data, reads no world and takes no argument, because the schema is fixed; the return is any because honest-persist owns the manifest type
    And it is reached by import so honest-persist's migration can create the three tables from one declared shape, and the module's table-touching functions read their table name and columns from this manifest rather than hardcoding them
