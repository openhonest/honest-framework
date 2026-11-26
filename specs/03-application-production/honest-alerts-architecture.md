# honest-alerts: Architecture Specification

**Version:** 0.1 (Draft) **Date:** March 15, 2026 **Status:** Active **Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-alerts is the message passing layer of the Honest Framework. It is not a notification widget. It is an actor model implementation on top of honest-state, honest-persist, and honest-observe.

The core principle: **messages pass between actors; no actor shares state with another**. A message is sent once, lands in a recipient's mailbox, and persists there until a declared termination condition is met. Delivery channels (DOM, email, SMS, webhook) are transports. The message is independent of the channel.

### 1.1 What honest-alerts Owns

- The `Message` schema and all sub-schemas
- The `Actor` identity model
- The `AlertRoute` routing table schema
- The supervisor: the pure function that delivers messages based on routing table records
- The mailbox: a projection over honest-observe's event log
- The `send_and_wait()` coroutine primitive for request-reply chains
- The DOM actor: rendering pending messages as visual surfaces on the live page
- Message lifecycle state machine

### 1.2 What honest-alerts Does Not Own

- Event log storage — honest-observe
- State machine execution — honest-state
- Authentication of actor identity — honest-auth
- Visual surface styling
- Long-running process orchestration with complex suspension — honest-flow (forthcoming)

---

### 1.3 Python Unit 1 publication

The Python package `honest_alerts` lists exactly seven names in its literal `__all__`: the input doors `send`, `acknowledge`, and `register_message_type`, and the boundaryless exports `advance`, `mailbox`, `is_terminated`, and `alert_tables_schema`. Order is immaterial. Other existing package bindings remain available through explicit named imports.

## 2. Actors

An actor is anything in the system that can send or receive messages. Actors are identified by type and ID. There is no actor registry; actors are declared in routing table records.

### 2.1 Actor Types

**Human actors:**

| Type | Identity |
|---|---|
| `user` | Specific authenticated user by ID |
| `role` | Anyone currently holding a named role |
| `tenant` | All users in an organization |
| `admin` | All users with administrative access |
| `anonymous` | Unauthenticated visitor |

**Process actors:**

| Type | Identity |
|---|---|
| `chain` | A running chain instance by chain name + correlation ID |
| `state_machine` | A state machine instance by machine name + entity ID |
| `job` | A scheduled or triggered background job by job ID |
| `projection` | An honest-observe projection that has crossed a declared threshold |

**System actors:**

| Type | Identity |
|---|---|
| `framework` | honest-framework itself (startup, shutdown, health events) |
| `auth` | honest-auth (session expiry, security violation, login event) |
| `webhook_inbound` | An inbound webhook from an external system |

**Interface actors:**

| Type | Identity |
|---|---|
| `dom` | A specific user's live browser session (one per browser tab) |
| `email` | An email address |
| `sms` | A phone number |
| `webhook_outbound` | An external HTTP endpoint |
| `slack` | A Slack channel or DM |
| `teams` | A Microsoft Teams channel or chat |

### 2.2 Actor Identity Schema

```python
ActorRef = {
    "type":       String,    # one of the type values above
    "id":         String?,   # specific actor ID (null means "all of this type")
    "tenant_id":  String?,   # scopes resolution to a tenant
}
```

**Examples:**

```python
# Specific user
{ "type": "user", "id": "user_8f3a9c", "tenant_id": "acme_corp" }

# All managers in a tenant
{ "type": "role", "id": "manager", "tenant_id": "acme_corp" }

# All active DOM sessions (broadcast)
{ "type": "dom", "id": None }

# A specific chain instance waiting for a reply
{ "type": "chain", "id": "create_order:corr_9x2k" }

# External webhook
{ "type": "webhook_outbound", "id": "https://hooks.example.com/alert" }
```

---

## 3. The Message

A message is an immutable, typed record in honest-observe's event log. Every field that affects delivery, persistence, or lifecycle is declared in the message at send time. Nothing about message behavior is implicit.

### 3.1 Message Schema

```python
Message = {
    # Identity
    "message_id":      String,        # UUID v7 (time-ordered)
    "message_type":    String,        # dot-namespaced type: "approval.requested", "system.maintenance_notice"
    "message_version": String,        # schema version for this message type; a value from that type's declared closed set, passed by the caller, never defaulted implicitly

    # Routing
    "sender":          ActorRef,      # who sent this message
    "recipient":       ActorRef,      # who should receive it
    "channel":         String?,       # preferred delivery channel: "dom" | "email" | "sms" | "webhook" | "slack" | "teams" | null (supervisor decides)

    # Content
    "subject_label_id": String,       # i18n label ID for message subject
    "body_label_id":   String?,       # i18n label ID for message body
    "payload":         dict,          # structured data specific to this message type

    # DOM surface (when channel includes "dom")
    "dom_surface":     String?,       # "banner" | "toast" | "modal" | "badge" | "inline"
    "dom_target":      String?,       # CSS selector for inline placement

    # Reply expectation
    "reply_required":  Boolean,       # True if sender is waiting for a reply
    "reply_options":   [ReplyOption]?, # declared response options (approve/reject/dismiss/snooze)
    "resume_token":    String?,       # chain resume token if reply_required=True

    # Lifecycle
    "termination":     TerminationSpec, # how and when this message ends
    "ack_scope":       String,        # "session" | "actor" | "broadcast"

    # Timestamps
    "sent_at":         Integer,       # epoch seconds (UTC)
}
```

`message_version` is an explicit bounded value, never an implicit default. Each `message_type` declares a closed set of schema versions it supports. The caller passes one member of that set on every send, and honest-alerts never substitutes a default when it is absent. A `message_version` that is missing, or that falls outside the declared closed set for its `message_type`, is a fault, not a value honest-alerts fills in.

The `new_message_id` reader obtains UTC Unix epoch milliseconds from the native clock and reads two and eight bytes from the native entropy source. It interprets the entropy samples as unsigned big-endian integers and passes the milliseconds and both integers to the pure `uuid7_from_parts` function. From most significant to least significant bit, the function places the low 48 bits of the milliseconds, version bits `0111`, the low 12 bits of the first sample, variant bits `10`, and the low 62 bits of the second sample. It returns lowercase canonical hyphenated UUID text ([RFC 9562 §5.7](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7)). The reader returns that text and continues to own all clock and entropy reads.

### 3.2 ReplyOption

```python
ReplyOption = {
    "option_id":    String,    # machine-readable identifier: "approve" | "reject" | "dismiss" | "snooze" | custom
    "label_id":     String,    # i18n label for the button/action
    "style":        String?,   # "primary" | "secondary" | "danger" | "warning"
    "payload":      dict?,     # additional data attached to this reply option
}
```

### 3.3 TerminationSpec

A message terminates when exactly one of these conditions is met:

```python
TerminationSpec = {
    "condition":    String,    # "ttl" | "acknowledged" | "event" | "never"

    # ttl: message expires after N seconds from sent_at
    "ttl_seconds":  Integer?,

    # acknowledged: message expires when ack_scope conditions are met
    # (no additional fields needed — ack_scope on the message determines when "acknowledged" is met)

    # event: message expires when a specific event type is appended to honest-observe
    "event_type":   String?,   # e.g., "system.maintenance_completed"
    "event_filter": dict?,     # optional payload conditions the event must match

    # never: message persists until explicitly deleted (admin use only)
}
```

### 3.4 Acknowledgment Scope

`ack_scope` declares when an acknowledgment counts as "done":

| Value | Meaning |
|---|---|
| `"session"` | Acknowledged by this specific DOM session only. Other sessions of the same user still see it. |
| `"actor"` | Acknowledged by the recipient actor. All sessions of that actor stop seeing it. |
| `"broadcast"` | Acknowledged by any one recipient. All recipients stop seeing it. |

**Example:** An upgrade banner sent to all DOM sessions with `ack_scope: "actor"` disappears for a user on all their devices once they dismiss it on any one device.

---

## 3b. Message-Type Registration

There is no framework-level set of message versions. Each registering application owns the set of versions for the message types it defines, and declares that set to honest-alerts before it sends any message of that type.

### 3b.1 register_message_type

`register_message_type` is a door. The registering application calls it with a dot-namespaced `message_type` and the closed set of `message_version` values that type supports:

```
register_message_type(message_type, message_versions) → Result
```

- `message_type`: String, dot-namespaced (for example `"approval.requested"`).
- `message_versions`: a non-empty closed set of String version values the application supports for that `message_type`.

honest-alerts persists the registration in a registered-types store it owns (a module-owned table on the same database as the alerts tables and the event log). The store holds one `RegisteredType` record per `message_type`:

```python
RegisteredType = {
    "message_type":     String,     # dot-namespaced message type
    "message_versions": [String],   # the closed set of versions this type supports
}
```

### 3b.2 Validation at send time

`run_send` reads the registration for the message's `message_type` from the registered-types store and validates the message's `message_version` against the registered set. A `message_type` that is not registered, or a `message_version` that is not a member of the registered set for its type, is a client `Fault` (`category: "client"`). honest-alerts never substitutes a default version and never carries a framework-level version set; the only authority for which versions exist is the registering application's declaration.

### 3b.3 Re-registration

Registering a `message_type` that is already registered is defined, and the rule turns on whether the arriving whole declaration matches the existing one. `run_register_message_type` reads the existing registration for the `message_type` before it writes.

- **Byte-identical whole declaration: a no-op success.** When the arriving declaration (the `message_type` and its `message_versions` set, taken whole) is byte-identical to the stored registration, re-registration changes nothing and the door returns success. Registering the same declaration twice is safe.
- **Any difference: a refused `Fault`.** When the arriving declaration differs from the stored one in any way, honest-alerts refuses it and writes nothing. The refusal is a client `Fault` (`category: "client"`), carried by return as data in the framework fault convention (honest-errors): a record with at least a `code` and a `message`, recognized by its own shape, never raised and never wrapped in an envelope. It is a refused-class fault, wrong in itself rather than a passing condition: sending the same differing declaration again fails the same way, so it is never retryable, and the `message` says what to do instead, which is to change the arriving declaration to match the stored one or to remove the existing registration first. Its `detail` names the existing declaration against the arriving one (both `message_type` values and both `message_versions` sets), so the caller sees exactly what differs.

---

## 4. The Mailbox

A mailbox is not a data structure. It is a projection over honest-observe's event log. An actor's mailbox is the answer to: "which messages addressed to me have not yet terminated?"

### 4.1 Mailbox Projection Algorithm

`mailbox` and `is_terminated` are pure projections over the `events` set handed to them as a parameter. honest-alerts never queries honest-observe's raw event log: per the honest-observe spec section 6, a projection is the only way to read the log and there is no raw query interface for application code. The caller selects the event set through an honest-observe projection and passes it in as `events`; `mailbox` and `is_terminated` fold over exactly those events and read nothing else.

`ActorRef` is pure identity: it carries no `session_id`. A session is never a field of the actor. `acknowledge` takes the acknowledging session as an explicit parameter and records it on the `alert.acknowledged` event as data; the ack event carries no scope word. The message's `ack_scope` (section 3.4), with its three values `session`, `actor`, and `broadcast`, is the only scope vocabulary, and the fold dispatches on it.

`mailbox` and `is_terminated` take `viewing_session`, an explicit `SessionId` or `NOTHING`, never a defaulted optional. A `SessionId` identifies one DOM session. `NOTHING` is the waiter view: a suspended `send_and_wait` belongs to no DOM session, so it passes `NOTHING`. Session-scoped termination compares an ack's acking session against `viewing_session`, and `NOTHING` never equals anything, so a session dismissal never ends a waiter. Actor-scoped and broadcast-scoped termination ignore `viewing_session` and terminate for every viewer, the waiter included. None of this reads a session off `ActorRef`.

For event termination, compare the candidate event's timestamp to the message's `sent_at` as UTC epoch microseconds. Accept a legacy integer epoch-second timestamp or the canonical Honest Observe UTC string `YYYY-MM-DDTHH:MM:SS.ffffffZ` (Honest Observe §2.1). Convert integer seconds, including `sent_at`, to microseconds and preserve all six fractional digits from the string. Equality qualifies. An absent, malformed, or unsupported timestamp, including a boolean, excludes only that candidate. The projection continues considering later candidates and keeps its existing event-type and payload filters, acknowledgment scopes, and mailbox ordering.

```
FUNCTION mailbox(actor_ref, at_time, events, viewing_session):
    // viewing_session: SessionId | NOTHING (explicit, never defaulted).
    // All messages sent to this actor.
    sent ← events WHERE:
        event_type = "alert.sent"
        AND recipient matches actor_ref
        AND sent_at <= at_time

    // Filter out terminated messages
    pending ← []
    FOR EACH msg IN sent:
        IF NOT is_terminated(msg, actor_ref, at_time, events, viewing_session):
            pending.APPEND(msg)

    RETURN pending ORDER BY sent_at ASC

FUNCTION is_terminated(msg, actor_ref, at_time, events, viewing_session):
    // viewing_session: SessionId | NOTHING (explicit, never defaulted).
    spec ← msg.payload.termination

    IF spec.condition = "ttl":
        RETURN at_time > msg.payload.sent_at + spec.ttl_seconds

    IF spec.condition = "acknowledged":
        acks ← events WHERE:
            event_type = "alert.acknowledged"
            AND payload.message_id = msg.payload.message_id
        // Dispatch on the message ack_scope (section 3.4), the only scope
        // vocabulary, through a table with a no-match row, never an if ladder.
        // The ack event carries the acking session as data and no scope word.
        RETURN SCOPE_TERMINATED[msg.payload.ack_scope](acks, actor_ref, viewing_session)

    IF spec.condition = "event":
        terminating_events ← events WHERE:
            event_type = spec.event_type
            AND (spec.event_filter is null OR matches spec.event_filter)
            AND event_at_or_after(timestamp, msg.payload.sent_at)
        RETURN len(terminating_events) > 0

    IF spec.condition = "never":
        RETURN False

    RETURN False

// Scope dispatch table: one row per ack_scope value, plus a no-match row.
// Each row answers "has this message been acknowledged for this viewer?"
SCOPE_TERMINATED = {
    // session-scoped: terminated only when some ack's acking session equals
    // viewing_session. viewing_session = NOTHING (the waiter view) equals no
    // session, so a session dismissal never ends a waiting send_and_wait.
    "session":   (acks, actor_ref, viewing_session) →
                     viewing_session is not NOTHING
                     AND any ack WHERE ack.payload.session = viewing_session,

    // actor-scoped: one ack by the recipient actor terminates the message for
    // every viewer, the waiter (viewing_session = NOTHING) included.
    "actor":     (acks, actor_ref, viewing_session) →
                     any ack WHERE ack.payload.actor.id = actor_ref.id,

    // broadcast-scoped: one ack by any recipient terminates the message for
    // every viewer, the waiter (viewing_session = NOTHING) included.
    "broadcast": (acks, actor_ref, viewing_session) →
                     len(acks) > 0,

    // no-match row: ack_scope is bounded at message-build time (section 3.4),
    // so a value the table does not carry is a program bug, not client input;
    // the row returns a server Fault naming the accepted scopes and the one
    // that arrived, never a silent False.
    NO_MATCH:    (acks, actor_ref, viewing_session) →
                     Fault(code="unknown_ack_scope", category="server"),
}
```

### 4.2 DOM Actor Mailbox

The DOM actor's mailbox is queried on every page load, every HTMX swap, and whenever honest-observe fires an `alert.*` event. The DOM actor renders all pending messages as visual surfaces.

The HTMX integration uses Server-Sent Events (SSE) to push mailbox updates in real time without polling:

```html
<div hx-ext="sse"
     sse-connect="/api/alerts/stream"
     sse-swap="alert:new">
    <!-- Pending messages rendered here -->
</div>
```

When a new `alert.sent` event is appended to the log for the current user, the SSE stream pushes the rendered HTML fragment. When an `alert.acknowledged` or `alert.expired` event fires, the DOM actor removes the corresponding surface.

---

## 5. The Routing Table

The routing table is a set of honest-persist records that declare how each message type is delivered. The supervisor reads the routing table and produces a delivery plan. There is no listener registry. No actor registers itself to receive messages. Routing is entirely table-driven.

### 5.1 AlertRoute Schema

```python
AlertRoute = {
    # Identity
    "route_id":       String,         # unique identifier

    # Matching
    "message_type":   String,         # which message type this route handles (supports wildcard: "system.*")
    "sender_type":    String?,        # optional: only match messages from this sender type

    # Delivery
    "channels":       [ChannelConfig], # how to deliver

    # Escalation
    "escalation":     EscalationRule?, # what happens if no ack within escalation_ttl

    # Priority
    "priority":       Integer,        # lower = higher priority; determines channel order
}

ChannelConfig = {
    "channel":        String,         # "dom" | "email" | "sms" | "webhook" | "slack" | "teams"
    "recipient_spec": ActorRef?,      # override recipient for this channel (e.g., always email the admin)
    "template_id":    String?,        # message template for this channel
    "delay_seconds":  Integer?,       # deliver after N seconds (0 = immediate)
}

EscalationRule = {
    "ttl_seconds":    Integer,        # escalate if no ack within this window
    "escalate_to":    ActorRef,       # forward to this actor on escalation
    "escalate_channel": String?,      # use this channel for escalation
    "escalation_message_type": String?, # override message type on escalation
}
```

### 5.2 Example Routes

```python
# System maintenance banner: sent to all DOM sessions, expires on maintenance_completed event
{
    "route_id":     "system_maintenance",
    "message_type": "system.maintenance_notice",
    "channels": [
        { "channel": "dom", "recipient_spec": { "type": "dom", "id": None } }
    ],
    "priority": 1,
}

# Approval request: DOM + email with 24h escalation to admin
{
    "route_id":     "approval_request",
    "message_type": "approval.requested",
    "channels": [
        { "channel": "dom" },
        { "channel": "email", "delay_seconds": 300 },  # email if not seen in 5 min
    ],
    "escalation": {
        "ttl_seconds":   86400,
        "escalate_to":   { "type": "role", "id": "admin" },
        "escalate_channel": "email",
    },
    "priority": 2,
}

# Security alert: immediate email + SMS, no DOM
{
    "route_id":     "security_alert",
    "message_type": "auth.security_violation",
    "channels": [
        { "channel": "email" },
        { "channel": "sms" },
    ],
    "priority": 1,
}
```

---

## 6. The Supervisor

The supervisor is a pure function. It takes a message and the routing table, produces a delivery plan, and executes it. It has no memory between invocations. It is stateless.

In unit 1, `supervise` returns a `DeliveryPlan` and declares no Fault arm: the match is assumed non-empty, so there is nothing for it to fault on. The `alert.no_route` Fault arm (the empty-match case below) arrives in a later unit that adds no-route handling; until then `supervise`'s return type is `DeliveryPlan` alone.

### 6.1 Supervisor Algorithm

```
FUNCTION supervise(message, routing_table):
    // Find matching routes
    routes ← routing_table WHERE:
        route.message_type matches message.message_type
        AND (route.sender_type is null OR route.sender_type = message.sender.type)

    routes ← SORT routes BY priority ASC

    IF routes is empty:
        // A fault, not a quiet success: the orchestrator decides whether to raise it or log it.
        RETURN err({
            code:     "alert.no_route",
            category: "server",
            message:  "No route delivers message type " + message.message_type
                      + "; add an AlertRoute whose message_type matches it",
            results:  [],
            detail:   { message_type: message.message_type },
        })

    delivery_results ← []

    FOR EACH route IN routes:
        FOR EACH channel_config IN route.channels:
            // Resolve recipient
            recipient ← channel_config.recipient_spec OR message.recipient

            // Build delivery record
            delivery ← {
                "message_id":    message.message_id,
                "route_id":      route.route_id,
                "channel":       channel_config.channel,
                "recipient":     recipient,
                "deliver_at":    now() + channel_config.delay_seconds,
                "status":        "pending",
            }

            // Write delivery record to honest-persist
            result ← honest_persist.insert("alert_deliveries", delivery)
            delivery_results.APPEND(result)

    // Emit alert.sent event to honest-observe
    await emit(
        event_type     = "alert.sent",
        aggregate_type = "alert",
        aggregate_id   = message.message_id,
        payload        = message,
        context        = {},
    )

    RETURN ok({ delivered: len(delivery_results) })
```

`supervise` is the pure function above: it reads the routing table and the message and returns a delivery plan or a Fault, writing nothing. The orchestrator `run_send` performs the writes, and it performs them atomically. `run_send` writes the delivery rows and appends the `alert.sent` event on one connection, inside one transaction: they commit together or roll back together, and a rolled-back transaction is returned as a Fault. The event log and the alerts tables live in the same database, which is what makes one transaction across both possible. `alert.sent` is the read-path source of truth for the mailbox, not telemetry, so its append must share the fate of the delivery rows.

`conn` is a standard DB-API connection (PEP 249): the alerts-owned tables and the event log are reached through the same `conn`, and `run_send` writes the delivery rows then appends `alert.sent` on that one `conn` and commits once, so the two writes land together or not at all. A write that fails before the single commit leaves nothing committed and returns a Fault. The conformance tests exercise this against a real in-memory SQLite connection, both the clean path (one commit, rows and `alert.sent` both present) and the failed-append path (nothing committed, a Fault returned).

Until honest-observe ships a transactional append that joins the caller's connection without committing on its own, honest-alerts uses a declared fallback: `run_send` writes the delivery rows first, then appends `alert.sent` through the emit seam, and a failed append is returned as a surfaced Fault. The order is rows first, then append, never emit-first, and a failed append is never swallowed.

A Fault returned by honest-alerts follows the framework fault convention: it is a record carrying at least a `code` and a `message`, returned as an ordinary value and recognized by its own shape, never raised and never wrapped in an envelope (honest-errors). When a Fault carries `category`, `category` is a bounded value, never free text: it is one of the closed set honest-type defines in its Fault schema (section 13.2), `"client"` or `"server"`. honest-type treats a Fault with no `category` as itself a server error, so `category`, where present, is always one of those two declared values.

### 6.2 Delivery Execution

A separate boundary process reads pending delivery records and executes them:

```
FUNCTION execute_deliveries():
    pending ← honest_persist.query(
        "alert_deliveries",
        WHERE status = "pending" AND deliver_at <= now()
    )

    FOR EACH delivery IN pending:
        channel_handler ← get_channel_handler(delivery.channel)
        result ← await channel_handler.deliver(delivery)

        IF "ok" IN result:
            honest_persist.update("alert_deliveries", delivery.id,
                { status: "delivered", delivered_at: now() })
            await emit("alert.delivered", "alert", delivery.message_id, delivery)
        ELSE:
            honest_persist.update("alert_deliveries", delivery.id,
                { status: "failed", error: result["err"] })
            await emit("alert.delivery_failed", "alert", delivery.message_id, delivery)
```

Channel handlers are pure functions registered per channel type. Adding a new channel type (e.g., PagerDuty) requires only a new handler registration; no supervisor logic changes.

---

## 6b. Fault codes

Every Fault honest-alerts returns is built by `alerts_fault` and carries a `code`, a bounded `category` (`client` or `server`, honest-type section 13.2), a `message`, and a `detail`. The full set of codes, with the category and the condition that raises each:

| Code | Category | Raised when |
|---|---|---|
| `unregistered_message_type` | client | A send names a `message_type` that has no registration in the registered-types store. |
| `message_version_not_registered` | client | A send's `message_version` is not a member of the registered set for its `message_type`. |
| `missing_message_version` | client | A send carries no `message_version`. |
| `invalid_termination` | client | A message's `termination` has fields that do not match its declared `condition`. |
| `invalid_registration` | client | The arriving registration has a malformed message type or an empty version set. |
| `refused_registration` | client | `register_message_type` receives, for an already-registered `message_type`, a declaration that differs from the stored one. The `detail` names the existing declaration and the arriving one. A byte-identical declaration is a no-op success, not this Fault. |
| `registration_write_failed` | server | The registered-types store write fails during `run_register_message_type`. |
| `append_failed` | server | `run_send`'s `alert.sent` append to the event log fails; the single transaction is rolled back and this Fault is returned, with no delivery rows committed. |
| `ack_append_failed` | server | `run_acknowledge`'s `alert.acknowledged` append fails. |
| `unknown_ack_scope` | server | The scope-termination dispatch receives an `ack_scope` the table does not carry. `ack_scope` is bounded at message-build time, so this can only be a program bug, never client input. |
| `unknown_termination_condition` | server | The termination-condition dispatch receives a condition outside its declaration. |
| `invalid_transition` | server | `advance` receives a `(state, event)` pair the lifecycle transition table does not declare. |

The pure registration validator reports the supplied `message_type` and `message_versions` in `invalid_registration` detail, and the full `existing` and `arriving` records in `refused_registration` detail. The message validator reports `message_type` for an unregistered type. Version faults carry `message_type` and `message_version`, which is the absence value for `missing_message_version` and the rejected version for `message_version_not_registered`. The lifecycle `invalid_transition` detail carries `state` and `event`. The acknowledgment-scope and termination-condition dispatch misses carry `accepted` for the declared alternatives and `arrived` for the unmatched value.

A `client` code marks input the caller can correct; a `server` code marks a program or infrastructure fault the caller cannot. honest-alerts returns every one of these as data, by return, never raised.

A successful `write_delivery` returns `{ok: true}` after inserting the row. It leaves the commit to the send transaction. On an `append_failed` Fault, `detail.message_id` is the generated message ID. On an `ack_append_failed` Fault, `detail.message_id` is the supplied message ID and `detail.observe` is the code of the append Fault returned by the emit seam.

When the Alerts emit seam converts a raised append failure into `emit_seam_failed`, that result has category `server`. Its `detail.aggregate_id` and `detail.event_type` identify the attempted append, and `detail.detail` carries the exception text. An Observe Fault returned as a value passes through the seam unchanged.

## 7. Message Lifecycle State Machine

Every message instance has a lifecycle governed by this state machine:

```python
alert_lifecycle = state_machine(
    name    = "alert_lifecycle",
    states  = vocabulary({ "alert_state": {
        "created", "delivered", "read", "acknowledged",
        "actioned", "escalated", "expired", "failed"
    }}),
    events  = vocabulary({ "alert_event": {
        "deliver", "read", "acknowledge", "action",
        "escalate", "expire", "fail"
    }}),
    initial  = "created",
    terminal = ["acknowledged", "actioned", "expired", "failed"],
    transitions = {
        ("created",    "deliver"):    "delivered",
        ("created",    "fail"):       "failed",
        ("created",    "expire"):     "expired",
        ("delivered",  "read"):       "read",
        ("delivered",  "acknowledge"): "acknowledged",
        ("delivered",  "action"):     "actioned",
        ("delivered",  "escalate"):   "escalated",
        ("delivered",  "expire"):     "expired",
        ("read",       "acknowledge"): "acknowledged",
        ("read",       "action"):     "actioned",
        ("read",       "escalate"):   "escalated",
        ("read",       "expire"):     "expired",
        ("escalated",  "acknowledge"): "acknowledged",
        ("escalated",  "action"):     "actioned",
        ("escalated",  "expire"):     "expired",
    }
)
```

State transitions produce events in honest-observe: `alert.delivered`, `alert.read`, `alert.acknowledged`, `alert.actioned`, `alert.escalated`, `alert.expired`, `alert.failed`. These events feed back into the mailbox projection.

---

## 8. send() and send_and_wait()

### 8.1 send()

The primary send function. Fire and forget (with respect to the sender).

```
send(message_type, recipient, payload, opts, context) → Result
```

`opts` is a closed bag of the `Message` fields the caller controls that are not already supplied by the explicit parameters. Every key it may carry is named below, with its type and allowed values drawn from the `Message` schema (section 3.1) and its sub-schemas. `opts` carries no other keys.

| opts key | Type | Allowed values |
|---|---|---|
| `message_version` | String | A member of the `message_type`'s declared closed set of schema versions (section 3.1). The caller passes it; it is never defaulted. |
| `subject_label_id` | String | An i18n label ID for the message subject. |
| `body_label_id` | String? | An i18n label ID for the message body, or null. |
| `channel` | String? | `"dom"` \| `"email"` \| `"sms"` \| `"webhook"` \| `"slack"` \| `"teams"` \| null (null lets the supervisor choose). |
| `dom_surface` | String? | `"banner"` \| `"toast"` \| `"modal"` \| `"badge"` \| `"inline"`, or null. |
| `dom_target` | String? | A CSS selector for inline placement, or null. |
| `reply_options` | [ReplyOption]? | A list of declared `ReplyOption` records (section 3.2), or null. |
| `termination` | TerminationSpec | A `TerminationSpec` (section 3.3) naming exactly one of `"ttl"` \| `"acknowledged"` \| `"event"` \| `"never"`. |
| `ack_scope` | String | `"session"` \| `"actor"` \| `"broadcast"` (section 3.4). |

`message_id`, `sender`, `sent_at`, `reply_required`, and `resume_token` are never passed in `opts`. `message_id` and `sent_at` are generated at send time, `sender` is taken from `context`, and `reply_required` with `resume_token` are set by the door that was called: `send()` leaves `reply_required` False, and `send_and_wait()` sets it True and generates the `resume_token` (section 8.3).

```python
@link(accepts=order_vocab, emits=order_vocab, boundary=True)
async def notify_order_placed(manifest):
    result = await honest_alerts.send(
        message_type = "order.placed",
        recipient    = { "type": "user", "id": manifest["customer_id"] },
        payload      = {
            "order_id":    manifest["order_id"],
            "total":       manifest["total"],
            "currency":    manifest["currency"],
        },
        opts = {
            "dom_surface":  "toast",
            "termination":  { "condition": "ttl", "ttl_seconds": 10 },
            "ack_scope":    "session",
        },
        context = manifest,
    )
    RETURN ok(manifest)
```

### 8.2 send_and_wait()

`send_and_wait` and its reply path are a later unit, not unit 1. Unit 1 declares no `send_and_wait` path: no `send_and_wait` or `run_send_and_wait` function, no reply-subscription reader, no `ReplyResult` or reply-status vocabulary, and no reply-event input side. This section describes the later unit; the paragraphs below stand as its specification.

Sends a message and suspends the coroutine until a reply arrives or the TTL expires. Uses the language's native `async/await` coroutine support. No thread is blocked.

```
send_and_wait(message_type, recipient, payload, opts, context) → Result
```

The result contains:
- `status`: `"replied"` | `"timeout"`
- `option_id`: which reply option the actor chose (if `status = "replied"`)
- `actor_id`: which actor replied
- `payload`: any additional payload attached to the reply

```python
@link(accepts=approval_vocab, emits=approval_vocab, boundary=True)
async def request_manager_approval(manifest):
    result = await honest_alerts.send_and_wait(
        message_type = "approval.requested",
        recipient    = { "type": "role", "id": "manager", "tenant_id": manifest["tenant_id"] },
        payload      = {
            "request_id":      manifest["request_id"],
            "request_summary": manifest["request_summary"],
            "requested_by":    manifest["user_id"],
        },
        opts = {
            "reply_options": [
                { "option_id": "approve", "label_id": "alerts.approve", "style": "primary" },
                { "option_id": "reject",  "label_id": "alerts.reject",  "style": "danger" },
            ],
            "termination": { "condition": "ttl", "ttl_seconds": 86400 },
            "dom_surface": "modal",
        },
        context = manifest,
    )

    IF result["status"] == "timeout":
        RETURN err({ code: "approval_timeout", category: "client" })

    IF result["option_id"] == "reject":
        RETURN err({
            code:     "approval_rejected",
            category: "client",
            message:  result["payload"].get("reason", "No reason given"),
        })

    RETURN ok({ **manifest, "approved_by": result["actor_id"] })
```

### 8.3 send_and_wait() Implementation

`send_and_wait()` uses a coroutine and honest-observe's event stream:

```
FUNCTION send_and_wait(message_type, recipient, payload, opts, context):
    // Send the message
    message ← build_message(message_type, recipient, payload, opts, context)
    message["reply_required"] ← True
    message["resume_token"]   ← generate_resume_token()

    send_result ← await send_message(message)

    // Subscribe to reply events for this message
    reply_event ← await wait_for_event(
        event_type   = "alert.replied",
        filter       = { "message_id": message.message_id },
        timeout      = opts.termination.ttl_seconds,
    )

    IF reply_event is None:    // timeout
        RETURN ok({ status: "timeout" })

    RETURN ok({
        status:    "replied",
        option_id: reply_event.payload.option_id,
        actor_id:  reply_event.payload.actor_id,
        payload:   reply_event.payload.reply_payload,
    })
```

honest-alerts does not import honest-observe for this. `send_and_wait` is handed an injected reply-subscription reader, declared in the honest-alerts module, that yields the matching `alert.replied` event (filtered by event type and `message_id`) or nothing on timeout. The host wires that reader to honest-observe's reply stream; honest-alerts only declares the reader and depends on its contract. When the matching event arrives the coroutine resumes, and no thread is held during the wait. The exact stream contract the host binds the reader to is owned by the send_and_wait unit, which is staged after unit 1.

---

## 9. DOM Actor Surfaces

When the recipient is a `dom` actor, the message is rendered as a visual surface on the live page. The surface type is declared on the message.

| Surface | Description | Default termination |
|---|---|---|
| `banner` | Full-width persistent bar at top of page | `"acknowledged"` or `"event"` |
| `toast` | Transient notification (bottom right) | `"ttl"` (default 5s) |
| `modal` | Blocking overlay requiring response | `"acknowledged"` |
| `badge` | Numeric count on a nav element | Persists until dismissed |
| `inline` | Rendered inside a specific `dom_target` element | `"acknowledged"` |

The DOM actor renders surfaces as HTMX fragments served from the honest-alerts endpoint. The surface HTML is server-rendered; no client-side component is needed.

### 9.1 Reply Handling from DOM

When a message has `reply_options`, the DOM surface renders action buttons. Clicking a button sends an HTMX request to the honest-alerts reply endpoint:

```
POST /api/alerts/{message_id}/reply
Body: { "option_id": "approve", "reply_payload": {} }
```

The reply endpoint:
1. Appends `alert.replied` to honest-observe with the option and actor
2. Appends `alert.acknowledged` to honest-observe
3. Returns an empty fragment that HTMX uses to remove the surface from the DOM

---

## 10. honest-observe Integration

All honest-alerts events flow through honest-observe. The complete event set:

| Event | When |
|---|---|
| `alert.sent` | Message created and queued for delivery |
| `alert.no_route` | No route matched the message type, so the message was not delivered. The supervisor returns this as a fault; the event is written when the orchestrator chooses to log it, through the output boundary that writes honest-observe's log |
| `alert.delivered` | Successfully delivered via a channel |
| `alert.delivery_failed` | Channel delivery failed |
| `alert.read` | DOM actor rendered the message (impression) |
| `alert.replied` | Recipient chose a reply option |
| `alert.acknowledged` | Message acknowledged (scope met) |
| `alert.actioned` | Message actioned (non-acknowledge response) |
| `alert.escalated` | Escalated due to TTL with no acknowledgment |
| `alert.expired` | TTL reached with no acknowledgment |
| `alert.failed` | Delivery failed across all channels |

The `alert.acknowledged` payload is an `AckPayload`, and its fields are named to match that record exactly: `message_id` (the acknowledged message), `actor` (an `ActorRef`, the acknowledging actor), `session` (the acknowledging session, a `SessionId` or `NOTHING`), `acknowledged_at` (the epoch-seconds time the acknowledgment happened), and `reply_payload` (any data attached to the acknowledgment, for example the chosen reply option's payload). The field is `actor`, carrying an `ActorRef`, never `actor_id`; and the field is `session`, never `session_id`. `acknowledged_at` is read at the boundary, by a reader on the input side, and passed in to the pure core; the pure core never calls `now()`. The payload carries no scope word (section 4.1).

These events are available for projections, dashboards, and further message triggers. An `alert.acknowledged` event can itself trigger another message send via an honest-observe projection rule.

---

## 10b. Alerts-owned tables in honest-persist

honest-alerts owns three tables, all in the same honest-persist database as the event log, so that `run_send` can write and append across both inside one transaction (section 6.1). The tables are `alert_routes` (the routing table, section 5), `alert_deliveries` (the delivery queue, section 6.2), and `alert_registered_types` (the message-type registry, section 3b). JSON columns hold the sub-records the schema types already define (`ChannelConfig`, `EscalationRule`, `ActorRef`, the version set), serialized as text, the way the event log holds `payload` as JSON.

```sql
CREATE TABLE alert_routes (
    route_id        TEXT        PRIMARY KEY,
    message_type    TEXT        NOT NULL,   -- supports a trailing wildcard, "system.*"
    sender_type     TEXT,                   -- nullable: match any sender type when null
    channels        TEXT        NOT NULL,   -- JSON, a list of ChannelConfig
    escalation      TEXT,                   -- JSON, an EscalationRule, nullable
    priority        INTEGER     NOT NULL,

    INDEX idx_alert_routes_type (message_type),
)

CREATE TABLE alert_deliveries (
    delivery_id     TEXT        PRIMARY KEY,
    message_id      TEXT        NOT NULL,
    route_id        TEXT        NOT NULL,
    channel         TEXT        NOT NULL,   -- "dom" | "email" | "sms" | "webhook" | "slack" | "teams"
    recipient       TEXT        NOT NULL,   -- JSON, an ActorRef
    deliver_at      INTEGER     NOT NULL,   -- epoch seconds (UTC)
    status          TEXT        NOT NULL,   -- "pending" | "delivered" | "failed"

    INDEX idx_alert_deliveries_due (status, deliver_at),
    INDEX idx_alert_deliveries_message (message_id),
)

CREATE TABLE alert_registered_types (
    message_type        TEXT    PRIMARY KEY,
    message_versions    TEXT    NOT NULL,   -- JSON, the closed set of version strings
)
```

Unlike the event log, these tables are not append-only: `alert_deliveries` rows move from `pending` to `delivered` or `failed` (section 6.2), and `alert_registered_types` accepts a byte-identical re-registration as a no-op (section 3b.3). honest-alerts exposes a pure schema-manifest function, the honest-alerts twin of honest-observe's `event_log_schema` (honest-observe section 10), that returns these three table manifests as data. It reads no world and takes no argument, because the schema is fixed, and it is reached by import so honest-persist's migration can create the tables from one declared shape. The boundary and reader functions that touch each table read their columns and table name from this manifest rather than hardcoding them: `write_delivery` and the delivery reader against `alert_deliveries`, `read_routes` against `alert_routes`, and `read_registered_type` and `write_registered_type` against `alert_registered_types`.

`run_send` writes the delivery rows to `alert_deliveries` and appends the `alert.sent` row to the event log on the one DB-API connection, and commits once: the rows and the `alert.sent` row commit together or roll back together (section 6.1).

---

## 11. Configuration

```toml
# honest-alerts.toml

[routing]
table = "alert_routes"         # honest-persist table for routing records
db_id = "primary"

[delivery]
table = "alert_deliveries"     # honest-persist table for delivery queue
poll_interval_seconds = 5      # how often to check for pending deliveries

[channels]
dom   = { enabled = true }
email = { enabled = false, smtp_config_id = "primary_smtp" }
sms   = { enabled = false, provider_config_id = "twilio" }
slack = { enabled = false, webhook_config_id = "ops_slack" }

[dom]
sse_endpoint = "/api/alerts/stream"
reply_endpoint = "/api/alerts/{message_id}/reply"

[send_and_wait]
default_ttl_seconds = 3600     # 1 hour default for reply waits
```

---

## 12. Conformance

### 12.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | `send()` with DOM channel; mailbox projection; message lifecycle state machine; `alert.*` events in honest-observe |
| **Full** | Core + `send_and_wait()` + escalation rules + email channel + routing table |
| **Complete** | Full + all channel types + multi-recipient broadcast + threshold-triggered sends from honest-observe projections |

### 12.2 Conformance Suite

The conformance suite is `python/honest-alerts/conformance/suite.json`, beside the module and run by its gate. Test cases cover:

- `send()` produces a valid `alert.sent` event with correct envelope
- Mailbox projection returns correct pending messages at a given timestamp
- Termination conditions correctly filter messages from mailbox
- `ack_scope` correctly determines when acknowledgment terminates a message
- Escalation fires after TTL with no acknowledgment
- `send_and_wait()` resumes coroutine on reply event
- `send_and_wait()` returns timeout status when TTL expires with no reply
- DOM surfaces are rendered for pending messages on page load
- Reply endpoint appends correct events and removes DOM surface
