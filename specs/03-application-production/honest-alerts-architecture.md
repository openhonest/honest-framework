# honest-alerts: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

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
    "message_version": String,        # schema version for this message type

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

## 4. The Mailbox

A mailbox is not a data structure. It is a projection over honest-observe's event log. An actor's mailbox is the answer to: "which messages addressed to me have not yet terminated?"

### 4.1 Mailbox Projection Algorithm

```
FUNCTION mailbox(actor_ref, at_time):
    // All messages sent to this actor
    sent ← events WHERE:
        event_type = "alert.sent"
        AND recipient matches actor_ref
        AND sent_at <= at_time

    // Filter out terminated messages
    pending ← []
    FOR EACH msg IN sent:
        IF NOT is_terminated(msg, actor_ref, at_time):
            pending.APPEND(msg)

    RETURN pending ORDER BY sent_at ASC

FUNCTION is_terminated(msg, actor_ref, at_time):
    spec ← msg.payload.termination

    IF spec.condition = "ttl":
        IF at_time > msg.payload.sent_at + spec.ttl_seconds:
            RETURN True

    IF spec.condition = "acknowledged":
        acks ← events WHERE:
            event_type = "alert.acknowledged"
            AND payload.message_id = msg.payload.message_id

        IF msg.payload.ack_scope = "session":
            RETURN any ack WHERE ack.payload.session_id = actor_ref.session_id

        IF msg.payload.ack_scope = "actor":
            RETURN any ack WHERE ack.payload.actor_id = actor_ref.id

        IF msg.payload.ack_scope = "broadcast":
            RETURN len(acks) > 0

    IF spec.condition = "event":
        terminating_events ← events WHERE:
            event_type = spec.event_type
            AND (spec.event_filter is null OR matches spec.event_filter)
            AND timestamp >= msg.payload.sent_at
        RETURN len(terminating_events) > 0

    IF spec.condition = "never":
        RETURN False

    RETURN False
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

### 6.1 Supervisor Algorithm

```
FUNCTION supervise(message, routing_table):
    // Find matching routes
    routes ← routing_table WHERE:
        route.message_type matches message.message_type
        AND (route.sender_type is null OR route.sender_type = message.sender.type)

    routes ← SORT routes BY priority ASC

    IF routes is empty:
        EMIT warning("alert.no_route", message.message_type)
        RETURN ok({ delivered: 0 })

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

`wait_for_event()` subscribes to honest-observe's SSE stream filtered by event type and payload conditions. When the matching event arrives, the coroutine resumes. No thread is held during the wait.

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
| `alert.no_route` | No route matched the message type; the message was not delivered (a warning) |
| `alert.delivered` | Successfully delivered via a channel |
| `alert.delivery_failed` | Channel delivery failed |
| `alert.read` | DOM actor rendered the message (impression) |
| `alert.replied` | Recipient chose a reply option |
| `alert.acknowledged` | Message acknowledged (scope met) |
| `alert.actioned` | Message actioned (non-acknowledge response) |
| `alert.escalated` | Escalated due to TTL with no acknowledgment |
| `alert.expired` | TTL reached with no acknowledgment |
| `alert.failed` | Delivery failed across all channels |

These events are available for projections, dashboards, and further message triggers. An `alert.acknowledged` event can itself trigger another message send via an honest-observe projection rule.

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

The conformance suite lives at `honest/honest-alerts-conformance/suite.json`. Test cases cover:

- `send()` produces a valid `alert.sent` event with correct envelope
- Mailbox projection returns correct pending messages at a given timestamp
- Termination conditions correctly filter messages from mailbox
- `ack_scope` correctly determines when acknowledgment terminates a message
- Escalation fires after TTL with no acknowledgment
- `send_and_wait()` resumes coroutine on reply event
- `send_and_wait()` returns timeout status when TTL expires with no reply
- DOM surfaces are rendered for pending messages on page load
- Reply endpoint appends correct events and removes DOM surface
