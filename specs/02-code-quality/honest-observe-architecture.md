# honest-observe: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-observe is the observability layer of the Honest Framework. It has six responsibilities:

1. **The event log** — an append-only, immutable record of everything that happened. The source of truth for all observability data. Backed by honest-persist.

2. **Automatic instrumentation** — the `@link` decorator and `@catch_at_boundary` emit framework events automatically. No developer logging code is required. Every function is its own print statement.

3. **Canonical request events** — one dense, structured event per request emitted at the boundary, colocating all request telemetry for zero-join incident response and analytics.

4. **Unified browser/server tracing** — browser-side events (attribute classifications, DOM state changes, HTMX requests) are beaconed to the same event log as server events via `sendBeacon()`. One log. Both sides. Joined by `request_id`.

5. **Projections** — pure functions that build the event log up into derived views: dashboards, metrics, timelines, running counts, audit trails.

6. **OpenTelemetry export** — one projection among many, emitting standard OTel traces, metrics, and logs to any compatible backend: Jaeger, Prometheus, Grafana, Datadog, Honeycomb, New Relic, Elastic, or any other OTel-compatible tool.

Events reach the log from three collection layers, each instrumented automatically with no developer code required:

- **Frontend:** honest-DOM beacons browser events via `sendBeacon()` to `/api/observe/ingest`. Every attribute classification, DOM state change, HTMX request, and HTMX response is recorded.
- **Middleware:** the intake middleware and `@catch_at_boundary` instrument the server boundary. Every chain execution, link execution, classification result, and canonical request summary is recorded.
- **Database:** honest-persist calls `emit_internal()` from inside `execute()`, `apply()`, and pool management. Every query, migration, pool event, and write queue stall is recorded.

One log. Three layers. Joined by `request_id`. No developer instrumentation required at any layer.

honest-observe does not define its own wire format, storage engine, or visualization layer. It defines the event contract, the projection interface, and the OTel mapping. Everything else is a projection.

### 1.1 Why Event Sourcing

honest-observe is built on event sourcing: every state change, every chain execution, every business event is an immutable fact appended to the log. The log is never modified. The current state of anything is derived by replaying the log.

This opens doors that are closed without event sourcing:

**Temporal queries.** What was the state of this subscription at 14:23 yesterday? Replay the log to that timestamp. No audit tables. No `updated_at` columns.

**Business intelligence without instrumentation.** Every business event is already in the log. Page views, abandon points, conversion rates, hotspots — all derivable from events without separate tracking code.

**Projections on demand.** A new question about the system requires a new projection, not a new database schema. Build the projection, replay the log, get the answer.

**Abandon detection.** A user who started a wizard but never completed it: `wizard_started` event exists, `wizard_completed` does not. No separate funnel tracking.

**OTel as one output among many.** The log is the source of truth. OTel is a projection of it.

### 1.2 What honest-observe Does Not Cover

- Storage engine selection — honest-persist handles this
- Visualization — build projections against any visualization tool
- Alerting rules — define thresholds in honest-persist records, not code
- Log retention policy — operator concern, not framework concern
- Security of the event log — honest-auth concern

---

## 2. The Event Envelope

Every event in the log, whether emitted by the framework automatically or by application code explicitly, uses the same envelope. The envelope has three clearly partitioned sections.

### 2.1 Framework Fields

Always present. Auth-agnostic. Defined by honest-observe.

```
event = {
    // Identity
    event_id:        String    — UUID v7 (time-ordered). Never reused.
    event_type:      String    — dot-namespaced identifier. e.g. "hf.chain.completed"
    event_version:   String    — schema version of this event type. e.g. "1.0"

    // Timing
    timestamp:       String    — ISO 8601 with microsecond precision, UTC
    sequence:        Integer   — always increasing, per aggregate_id

    // Aggregate
    aggregate_type:  String    — what kind of thing this event is about
                                 e.g. "order", "user", "chain", "link"
    aggregate_id:    String    — identifier of the specific thing

    // Content
    payload:         dict      — event-type-specific data. Open schema.
                                 Defined per event type in section 4.

    // Auth partition (see section 2.2)
    auth:            dict      — see below

    // Application metadata (see section 2.3)
    meta:            dict?     — see below
}
```

### 2.2 Auth Partition

**This section is owned by the authentication layer in use.** Applications not using honest-auth must replace this entire section with their own auth fields or omit it. The partition boundary is the `auth` key. Nothing inside `auth` is read by the framework for any purpose other than attaching it to the event record.

**When using honest-auth:**

```
auth = {
    // Who made the call
    caller_id:         String    — authenticated user or service identity
    caller_session:    String    — session factor ID from honest-auth

    // Whose data was affected
    data_owner_id:     String    — owner of the aggregate being acted upon

    // Zero-trust evidence
    factors_presented: [String]  — list of factor types validated for this request
                                   e.g. ["session", "data", "device"]
    request_signature: String    — HMAC signature from honest-auth request

    // Provenance
    ip_address:        String?   — originating IP if available
    user_agent:        String?   — originating user agent if available
}
```

**When using a different auth system:**

Replace the `auth` block entirely. The field names and semantics are yours to define. The framework never reads `auth.*` fields — it only carries them forward into the log and into projections that explicitly request them.

Document your auth fields in your own spec and tell honest-observe to use your block:

```python
# honest-observe config
honest_observe_config = {
    "auth_provider": "custom",
    "auth_fields": ["user_id", "session_token", "tenant_id"],
}
```

**When using no auth:**

Omit the `auth` key entirely. honest-observe will log a warning if a framework event is emitted without an auth block, but will not reject it.

### 2.3 Application Metadata

Optional. Open schema. For anything the application wants to attach that is not part of the event's business meaning.

```
meta = {
    environment:   String?   — "production", "staging", "development"
    tenant_id:     String?   — for multi-tenant applications
    release:       String?   — application release version
    feature_flags: dict?     — active feature flags at event time
    correlation_id: String?  — external request ID for cross-system tracing
    // ... anything else
}
```

### 2.4 Event Envelope Schema

```json
{
    "event_id":       "019x2k...",
    "event_type":     "hf.chain.completed",
    "event_version":  "1.0",
    "timestamp":      "2026-03-15T14:23:07.441832Z",
    "sequence":       1042,
    "aggregate_type": "chain",
    "aggregate_id":   "create_user_pipeline",
    "payload": {
        "duration_ns":    441832,
        "link_count":     5,
        "fault_code":     null,
        "result":         "ok"
    },
    "auth": {
        "caller_id":         "user_8f3a9c",
        "caller_session":    "sess_7x2m...",
        "data_owner_id":     "user_8f3a9c",
        "factors_presented": ["session", "data"],
        "request_signature": "sha256:a3f9..."
    },
    "meta": {
        "environment":    "production",
        "release":        "2026.03.15.1",
        "correlation_id": "req_9x2k..."
    }
}
```

---

## 3. emit()

`emit()` is the one function that writes events to the log. It is always called inside a chain link declared `boundary=True`.

```
emit(event_type, aggregate_type, aggregate_id, payload, context, runtime) → Result
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `event_type` | String | Dot-namespaced event type identifier |
| `aggregate_type` | String | What kind of thing this event is about |
| `aggregate_id` | String | Identifier of the specific thing |
| `payload` | dict | Event-type-specific data |
| `context` | dict | The current manifest. honest-observe extracts `auth` and `meta` from it using the configured field names. |
| `runtime` | Runtime | The boundary's one collaborator — see below. |

**The `runtime` collaborator.** Everything `emit` cannot compute purely is reached through one injected object, never read from a global or a clock and never imported. It supplies the impure values — `event_id()`, `timestamp()`, `sequence(aggregate_id)` — the config — `version(event_type)`, `auth_fields`, `meta_fields` — and the **log writer**, `append(event)`. Injecting `append` is what keeps honest-observe a leaf above persist: observe is *stored by* persist but never *imports* it, so the dependency runs one way (persist → observe), with no cycle. It is also why `emit` is testable without a database — a stand-in runtime returns canned values and records what was appended.

**Return:**

`ok({ event_id: "..." })` on success. `err({ code: "emit_failed", ... })` if the log write fails, or the envelope's own validation fault if a required field is empty. The caller decides whether to propagate the fault.

**Algorithm:**

```
FUNCTION emit(event_type, aggregate_type, aggregate_id, payload, context, runtime):   -- async
    built ← build_event(                                  -- the pure assembly + validation (section 2)
        event_type, runtime.version(event_type),
        aggregate_type, aggregate_id, payload,
        runtime.event_id(), runtime.timestamp(), runtime.sequence(aggregate_id),
        auth = extract_auth(context, runtime.auth_fields),
        meta = extract_meta(context, runtime.meta_fields),
    )
    IF "err" IN built: RETURN built                       -- an empty required field; nothing is written

    event ← built["ok"]
    written ← await runtime.append(event)                 -- the one I/O step
    IF "err" IN written:
        RETURN err({ code: "emit_failed", category: "server",
                     message: "Failed to append event to the log", detail: written["err"] })
    RETURN ok({ event_id: event.event_id })
```

`emit` is async because the append is I/O. It does not catch: `append` returns a Result, and `emit` threads it. The impure value generators (`event_id`, `timestamp`, `sequence`) are synchronous calls on the runtime; only the append is awaited.

**Usage in a chain link:**

```python
@link(accepts=order_vocab, emits=order_vocab, boundary=True)
async def record_order_placed(manifest):
    result = await emit(
        event_type      = "order.placed",
        aggregate_type  = "order",
        aggregate_id    = manifest["order_id"],
        payload         = {
            "items":       manifest["items"],
            "total":       manifest["total"],
            "currency":    manifest["currency"],
        },
        context         = manifest,
        runtime         = observe_runtime,    // the injected boundary collaborator
    )

    IF "err" IN result:
        RETURN result    // emit failure propagates up the chain

    RETURN ok(manifest)
```

### 3.1 emit() is Always at a Boundary

`emit()` writes to a database. It is I/O. It must always be called inside a link declared `boundary=True`. honest-check enforces this: calling `emit()` inside a non-boundary link is an HC-P004 violation.

### 3.2 Sequence Numbers

Sequence numbers are per-aggregate and always increasing. They fix the order within an aggregate without needing global locks. Two events with the same `aggregate_id` will have different sequence numbers. Two events with different `aggregate_ids` may have identical sequence numbers.

Sequence numbers are supplied through the runtime's `sequence(aggregate_id)` — a per-aggregate counter the runtime owns (typically persist-backed). The implementation is language-idiomatic; the contract is that sequence numbers are unique and increasing within an aggregate. `emit` only calls it; it never owns the counter.

---

## 4. Framework Events

The framework emits a fixed set of events automatically. These require no application code. honest-observe instruments them from `@link` and `chain()` declarations.

### 4.1 Chain Events

**`hf.chain.started`**
```
aggregate_type: "chain"
aggregate_id:   chain_name
payload: {
    chain_name:    String,
    link_count:    Integer,
    input_types:   [String],   // vocabulary type names in the input manifest
}
```

**`hf.chain.completed`**
```
aggregate_type: "chain"
aggregate_id:   chain_name
payload: {
    chain_name:    String,
    duration_ns:   Integer,
    link_count:    Integer,
    result:        "ok" | "err",
    fault_code:    String?,    // present if result = "err"
    fault_category: String?,   // "client" | "server"
}
```

### 4.2 Link Events

**`hf.link.executed`**
```
aggregate_type: "link"
aggregate_id:   link_name
payload: {
    link_name:       String,
    chain_name:      String,
    duration_ns:     Integer,
    result:          "ok" | "err",
    fault_code:      String?,
    boundary:        Boolean,

    // Honest-framework-specific measurements (no OTel equivalent)
    mutations:       Integer,   // count of manifest field mutations detected
    singletons:      Integer,   // count of singleton accesses detected
    nondeterminism:  Boolean,   // true if time/random/uuid call detected
    io_calls:        Integer,   // count of I/O calls (boundary=True links only)
}
```

**`hf.link.faulted`**
```
aggregate_type: "link"
aggregate_id:   link_name
payload: {
    link_name:     String,
    chain_name:    String,
    fault_code:    String,
    fault_category: String,
    fault_message: String,
    input_manifest: dict?,   // included at ERROR severity only, configurable
}
```

### 4.3 Classification Events

**`hf.classify.completed`**
```
aggregate_type: "classify"
aggregate_id:   vocabulary_name
payload: {
    vocabulary_name:  String,
    token_count:      Integer,
    rejection_count:  Integer,
    duration_ns:      Integer,
    rejection_reasons: { reason_code: count },
}
```

### 4.4 State Machine Events

**`hf.state.transitioned`**
```
aggregate_type: "state_machine"
aggregate_id:   machine_name + ":" + entity_id
payload: {
    machine_name:  String,
    entity_id:     String,
    from_state:    String,
    event:         String,
    to_state:      String,
    duration_ns:   Integer,
}
```

**`hf.state.rejected`**
```
aggregate_type: "state_machine"
aggregate_id:   machine_name + ":" + entity_id
payload: {
    machine_name:  String,
    entity_id:     String,
    current_state: String,
    event:         String,
    fault_code:    String,   // "no_transition" | "invalid_state" | "invalid_event" | "terminal_state"
}
```

### 4.5 honest-persist Events

All honest-persist events are emitted directly from inside honest-persist boundary functions — not via middleware. `execute()` emits `hf.persist.query`, `apply()` emits `hf.persist.migration`, pool management emits `hf.persist.pool`. See `honest-persist-architecture.md §8.5–8.8` for the emit algorithms.

**`hf.persist.query`**
```
aggregate_type: "persist"
aggregate_id:   db_id + ":" + table_name
payload: {
    db_id:          String,
    table_name:     String,
    operation:      "select" | "insert" | "update" | "delete" | "raw",
    row_count:      Integer,
    duration_ns:    Integer,
    sql_hash:       String,    -- always present
    sql:            String?,   -- development mode only
    request_id:     String?,   -- join key to hf.request.canonical
    fault_code:     String?,
}
```

**`hf.persist.migration`**
```
aggregate_type: "schema"
aggregate_id:   db_id + ":" + table_name
payload: {
    db_id:        String,
    operation:    String,    -- "create_table" | "add_column" | "alter_column" | etc.
    table:        String,
    detail:       dict,      -- operation-specific detail
    duration_ns:  Integer,
    sql:          String,    -- the DDL executed
    success:      Boolean,
    fault_code:   String?,
}
```

**`hf.persist.pool`**
```
aggregate_type: "pool"
aggregate_id:   db_id
payload: {
    db_id:       String,
    event:       "created" | "exhausted" | "retry" | "closed" | "error",
    pool_size:   Integer,
    active:      Integer,
    waiting:     Integer,
    duration_ns: Integer?,
    fault_code:  String?,
    message:     String?,
}
```

**`hf.persist.queue_stalled`**
```
aggregate_type: "persist"
aggregate_id:   db_id
payload: {
    db_id:           String,
    stalled_writes:  Integer,   -- count of queued writes not yet persisted
    stalled_since:   String,    -- ISO timestamp of first stalled write
    oldest_write_ns: Integer,   -- age of oldest pending write in nanoseconds
}
```

Emitted when the optimistic write queue has not successfully flushed for 6 hours. Never silent.

### 4.6 Canonical Request Event

The canonical request event is one dense, structured event emitted by `@catch_at_boundary` at the end of every request. It colocates all request telemetry in a single record: no joins required to answer operational questions.

This is the honest-framework equivalent of Stripe's canonical log line: every meaningful fact about a request in one place, queryable directly, archivable for long-term analytics.

**`hf.request.canonical`**
```
aggregate_type: "request"
aggregate_id:   request_id
payload: {
    // HTTP
    http_method:      String,         // "GET" | "POST" | etc.
    http_path:        String,         // "/api/items"
    http_status:      Integer,        // 200 | 400 | 422 | 500

    // Identity
    caller_id:        String?,        // from auth partition
    session_id:       String?,        // from auth partition

    // Chain execution
    chain_name:       String?,        // primary chain executed
    link_count:       Integer,        // number of links executed
    link_sequence:    [LinkSummary],  // ordered list of links with results

    // Classification
    token_count:      Integer,        // tokens classified at intake
    rejection_count:  Integer,        // tokens rejected at intake

    // Persistence
    query_count:      Integer,        // database queries issued
    query_duration_ns: Integer,       // total time in database

    // Outcome
    result:           "ok" | "err",
    fault_code:       String?,
    fault_category:   String?,        // "client" | "server"

    // Timing
    duration_ns:      Integer,        // total request duration

    // Source
    request_id:       String,         // X-Request-ID, join key with browser events
    source:           "server",
}

LinkSummary = {
    link_name:    String,
    duration_ns:  Integer,
    result:       "ok" | "err",
    fault_code:   String?,
}
```

`@catch_at_boundary` assembles this record from events already in the log for this `request_id`. It is the last event written for every request.

### 4.7 Startup and Shutdown Events

The framework emits lifecycle events at startup and shutdown. These replace ad-hoc startup logging.

**`hf.app.started`**
```
aggregate_type: "app"
aggregate_id:   app_name
payload: {
    app_name:       String,
    release:        String?,
    environment:    String,
    chains_loaded:  Integer,
    links_loaded:   Integer,
    vocabs_loaded:  Integer,
}
```

**`hf.app.stopped`**
```
aggregate_type: "app"
aggregate_id:   app_name
payload: {
    app_name:    String,
    uptime_ns:   Integer,
    reason:      "graceful" | "signal" | "crash",
}
```

**`hf.app.error`**
```
aggregate_type: "app"
aggregate_id:   app_name
payload: {
    error_type:  String,    // exception class name
    message:     String,
    traceback:   String?,   // included in development; omitted in production
    context:     String?,   // where in startup/shutdown the error occurred
}
```

`hf.app.error` replaces unhandled exception logging. Any exception that escapes `@catch_at_boundary` or occurs outside a chain is caught at the application supervisor level and written as `hf.app.error`.

### 4.8 Proof Events

honest-test emits one proof event per function on every conformance run. Where every other framework event records what happened during a *request* at runtime, a proof event records that a function's stated behaviour was *verified* — putting the static "is this requirement proved?" thread into the same log as the runtime "what happened to this request?" thread.

The two threads use **different correlation keys**. Runtime events join on `request_id`. Proof events join on the function's fully-qualified name, which is also its one gherkin (the requirement statement, honest-gherkin §9.1) and its function-point unit (honest-gherkin §9.2). There is no `request_id` on a proof event — it is emitted at test time, outside any request.

**`hf.proof.checked`**
```
aggregate_type: "function"
aggregate_id:   function_fqn            // e.g. "honest_test.honesty._finding"
payload: {
    function:        String,            // fully-qualified function name (= aggregate_id)
    gherkin:         String,            // the one gherkin scenario stating this behaviour
    module:          String,            // owning module
    cases:           Integer,           // generated + contract cases run for this function
    result:          "proved" | "failed",
    failures:        [String],          // empty unless result = "failed"
    line_coverage:   Float,             // percent of the function's lines reached
    branch_coverage: Float,             // percent of the function's branches reached
}
```

The proof event is emitted through the injected runtime (section 3), exactly as any other `emit`: honest-test does not import honest-observe; the conformance runner wires `emit` in, and a pure local run with no runtime injected emits nothing. Because every function carries exactly one gherkin (HC-P009) and the run emits exactly one proof event per function, the proof events form a complete, gap-free **requirement → proof → result** matrix. It is read with the same tools as the runtime log (section 9), and the function-point count (honest-gherkin §9.2) is itself a projection over it: count the `hf.proof.checked` events, partition `proved` from `failed`.

---

## 5. Application Events

Application events are emitted explicitly by application chain links using `emit()`. The framework defines no schema for application events beyond the standard envelope. The application owns the event type namespace and the payload schema.

### 5.1 Naming Convention

Application event types use a reverse-domain-style namespace to avoid collisions with framework events (`hf.*`) and between applications:

```
{app_name}.{aggregate_type}.{verb}

// Examples:
order.placed
order.cancelled
subscription.started
subscription.payment_failed
user.wizard_started
user.wizard_step_completed
user.wizard_abandoned
document.exported
report.generated
```

### 5.2 Generic Examples

These examples are intentionally domain-agnostic to illustrate the pattern, not prescribe the schema.

**A multi-step wizard tracking example:**

```python
# Emitted when user starts a wizard
await emit(
    event_type     = "app.wizard.started",
    aggregate_type = "wizard",
    aggregate_id   = manifest["wizard_session_id"],
    payload        = {
        "wizard_type":   manifest["wizard_type"],
        "step_count":    manifest["total_steps"],
        "entry_point":   manifest["referrer"],
    },
    context        = manifest,
)

# Emitted at each step completion
await emit(
    event_type     = "app.wizard.step_completed",
    aggregate_type = "wizard",
    aggregate_id   = manifest["wizard_session_id"],
    payload        = {
        "step_number":   manifest["current_step"],
        "step_name":     manifest["step_name"],
        "duration_ns":   manifest["step_duration_ns"],
    },
    context        = manifest,
)

# Emitted on completion
await emit(
    event_type     = "app.wizard.completed",
    aggregate_type = "wizard",
    aggregate_id   = manifest["wizard_session_id"],
    payload        = {
        "total_steps":     manifest["total_steps"],
        "total_duration_ns": manifest["total_duration_ns"],
        "outcome":         manifest["outcome"],
    },
    context        = manifest,
)
```

**A subscription lifecycle example:**

```python
await emit(
    event_type     = "app.subscription.payment_failed",
    aggregate_type = "subscription",
    aggregate_id   = manifest["subscription_id"],
    payload        = {
        "plan":          manifest["plan"],
        "failure_reason": manifest["payment_failure_reason"],
        "attempt":       manifest["payment_attempt_count"],
        "provider":      manifest["payment_provider"],
        "provider_code": manifest["provider_error_code"],
    },
    context        = manifest,
)
```

**A page view / hotspot example:**

```python
await emit(
    event_type     = "app.page.viewed",
    aggregate_type = "page",
    aggregate_id   = manifest["route"],
    payload        = {
        "route":          manifest["route"],
        "time_on_page_ms": manifest["time_on_page_ms"],
        "scroll_depth_pct": manifest["scroll_depth_pct"],
        "interactions":   manifest["interaction_count"],
    },
    context        = manifest,
)
```

### 5.3 Abandon Detection Pattern

Abandon detection is a projection over two event types: the start event and the completion event. No special instrumentation is needed. The wizard that emits `app.wizard.started` but never emits `app.wizard.completed` within a configurable TTL is an abandoned wizard.

```python
# Projection: abandoned wizards
FUNCTION project_abandoned_wizards(event_log, ttl_hours=24):
    started    ← events WHERE event_type = "app.wizard.started"
    completed  ← SET of aggregate_ids WHERE event_type = "app.wizard.completed"
    cutoff     ← now() - timedelta(hours=ttl_hours)

    RETURN [
        e FOR e IN started
        WHERE e.aggregate_id NOT IN completed
        AND e.timestamp < cutoff
    ]
```

---

## 6. Projections

A projection is a pure function that reads a subset of the event log and produces a derived read model. Projections are the only way to read from honest-observe. There is no direct query interface on the raw event log for application code.

### 6.1 Projection Interface

```
FUNCTION project(
    event_types:  [String],    // filter: only these event types
    aggregate_type: String?,   // filter: only this aggregate type
    aggregate_id:  String?,    // filter: only this aggregate
    from:          timestamp?, // filter: events after this time
    to:            timestamp?, // filter: events before this time
    fold:          function,   // accumulator: (state, event) → state
    initial_state: any,        // starting state for fold
) → state
```

The projection fold is a pure function: it takes the current accumulated state and one event, and returns the new accumulated state. No I/O. No mutation.

### 6.2 Example Projections

**Subscription monitoring summary (d-me admin pattern):**

```python
def project_subscription_summary(days=7):
    cutoff = now() - timedelta(days=days)

    def fold(state, event):
        if event.event_type == "app.subscription.validation_checked":
            state["validation_total"] += 1
            if event.payload["result"] == "success":
                state["validation_successful"] += 1
        if event.event_type == "app.payment.api_called":
            state["payment_total"] += 1
            state["payment_duration_sum"] += event.payload["duration_ms"]
            if event.payload["result"] == "failure":
                state["payment_failed"] += 1
        return state

    return project(
        event_types    = ["app.subscription.validation_checked", "app.payment.api_called"],
        from           = cutoff,
        fold           = fold,
        initial_state  = {
            "validation_total": 0, "validation_successful": 0,
            "payment_total": 0, "payment_failed": 0, "payment_duration_sum": 0,
        }
    )
```

**Chain honesty score:**

```python
def project_honesty_score(chain_name, days=7):
    cutoff = now() - timedelta(days=days)

    def fold(state, event):
        state["total_executions"] += 1
        state["total_mutations"] += event.payload.get("mutations", 0)
        state["total_singletons"] += event.payload.get("singletons", 0)
        if event.payload.get("nondeterminism"):
            state["nondeterminism_count"] += 1
        return state

    return project(
        event_types    = ["hf.link.executed"],
        aggregate_type = "link",
        from           = cutoff,
        fold           = fold,
        initial_state  = {
            "total_executions": 0,
            "total_mutations":  0,
            "total_singletons": 0,
            "nondeterminism_count": 0,
        }
    )
```

**Login activity timeline (d-me admin pattern):**

```python
def project_login_trends(days=30):
    cutoff = now() - timedelta(days=days)

    def fold(state, event):
        date = event.timestamp[:10]
        state.setdefault(date, {"successful": 0, "failed": 0})
        if event.payload["result"] == "success":
            state[date]["successful"] += 1
        else:
            state[date]["failed"] += 1
        return state

    return project(
        event_types    = ["app.auth.login_attempted"],
        from           = cutoff,
        fold           = fold,
        initial_state  = {}
    )
```

### 6.3 Snapshot Projections

For aggregates with very many events (millions), replaying the full log on every request is too slow. honest-observe supports snapshot projections: the projection state is periodically persisted to honest-persist, and subsequent replays start from the snapshot rather than the beginning.

```
snapshot = {
    projection_id: String,      // identifies this projection
    snapshot_at:   timestamp,   // the log position this snapshot covers
    state:         dict,        // the folded state at this position
}
```

Snapshots are managed automatically when a projection is declared with `snapshot_interval`:

```python
subscription_summary = declare_projection(
    projection_id     = "subscription_summary",
    event_types       = [...],
    fold              = fold_function,
    initial_state     = {...},
    snapshot_interval = 1000,  // snapshot every 1000 events
)
```

---

## 7. OpenTelemetry Export

### 7.1 OTel is a Projection

The OTel exporter is a projection that reads the event log and emits OTel signals. It runs as a background process, not on the request path. Events are exported asynchronously.

```
hf.chain.started      → OTel Trace Span start
hf.chain.completed    → OTel Trace Span end (ok or error)
hf.link.executed      → OTel Trace child Span
hf.link.faulted       → OTel Span Event with status=ERROR
hf.persist.query      → OTel Trace child Span (db.* semantic conventions)
hf.classify.completed → OTel Metric counter
hf.state.transitioned → OTel Trace Span Event
```

### 7.2 OTel Semantic Conventions

Standard OTel attributes on framework spans:

| OTel Attribute | Source |
|---|---|
| `service.name` | honest-observe config |
| `service.version` | `meta.release` |
| `http.method` | from honest-py HTTP boundary link |
| `http.route` | from honest-py HTTP boundary link |
| `http.status_code` | from honest-py boundary result |
| `db.system` | from honest-persist event |
| `db.operation` | from `hf.persist.query` payload |
| `db.name` | from `hf.persist.query` aggregate_id |

### 7.3 honest-framework Semantic Conventions

These attributes extend OTel with honest-framework-specific measurements. They are namespaced under `hf.*` per OTel convention for non-standard attributes.

| Attribute | Type | Description |
|---|---|---|
| `hf.chain.name` | String | Chain identifier |
| `hf.chain.link_count` | Integer | Number of links in chain |
| `hf.chain.fault_code` | String | Fault code if chain errored |
| `hf.link.name` | String | Link function identifier |
| `hf.link.boundary` | Boolean | Whether link is declared boundary |
| `hf.link.mutations` | Integer | Count of manifest field mutations |
| `hf.link.singletons` | Integer | Count of singleton accesses |
| `hf.link.nondeterminism` | Boolean | Non-deterministic call detected |
| `hf.link.io_calls` | Integer | I/O call count (boundary links) |
| `hf.vocabulary.name` | String | Vocabulary used for classification |
| `hf.classify.rejection_count` | Integer | Tokens rejected during classification |
| `hf.state.machine` | String | State machine name |
| `hf.state.from` | String | Previous state |
| `hf.state.event` | String | Triggering event |
| `hf.state.to` | String | New state |
| `hf.auth.caller_id` | String | Caller identity (when honest-auth is used) |
| `hf.auth.data_owner_id` | String | Data owner identity (when honest-auth is used) |
| `hf.auth.factors_presented` | String[] | Auth factors validated |

### 7.4 OTel Integration Hooks

Each spoke implementation provides integration hooks for the OTel SDK. The developer installs the OTel exporter and configures the endpoint; the framework instruments automatically.

**Python (honest-py):**

```python
from honest_observe import install_otel_exporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

install_otel_exporter(
    exporter    = OTLPSpanExporter(endpoint="http://jaeger:4317"),
    service     = "my-application",
    environment = "production",
)
```

**JavaScript (honest-js):**

```javascript
import { installOtelExporter } from 'honest-observe'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'

installOtelExporter({
    exporter:    new OTLPTraceExporter({ url: 'http://jaeger:4318/v1/traces' }),
    service:     'my-application',
    environment: 'production',
})
```

Once installed, all `hf.*` events are automatically exported as OTel signals. No further configuration is required for standard instrumentation.

### 7.5 Zero-Code vs Code-Based Instrumentation

honest-observe provides both OTel instrumentation modes:

**Zero-code (automatic):** honest-observe's `@link` decorator and `chain()` constructor auto-instrument without any additional developer code. Install the exporter and you're done.

**Code-based (explicit):** Developers may add additional OTel spans or attributes to their chain links using the standard OTel API. These coexist with honest-observe's automatic instrumentation.

---

## 8. Browser Instrumentation

Browser-side events are beaconed to the same event log as server events. One log. Both sides. Joined by `request_id`. No separate browser monitoring stack.

### 8.1 The Mechanism: sendBeacon

`navigator.sendBeacon()` is the browser's fire-and-forget HTTP mechanism. It:

- Does not block the main thread
- Completes even if the page is navigating away or closing
- Has no response — the browser does not wait
- Is the browser's equivalent of UDP for telemetry

This is the correct mechanism for browser event emission. `fetch()` blocks; `sendBeacon()` does not. The application never pays for observability in page latency.

### 8.2 Browser Event Envelope

Browser events use the same envelope as server events with two additions: `source: "browser"` and `session_id`. The `request_id` field joins browser events to the server events they triggered.

```
browser_event = {
    event_id:       String    — UUID v4, generated in browser
    event_type:     String    — dot-namespaced: "hf.browser.*" or "hf.dom.*"
    event_version:  String    — "1.0"
    timestamp:      String    — ISO 8601, from performance.timeOrigin + performance.now()
    source:         "browser"
    session_id:     String    — from honest-auth session cookie (read-only, not secret)
    request_id:     String?   — from last X-Request-ID response header; joins to server events
    payload:        dict      — event-type-specific data
}
```

### 8.3 Ingest Endpoint

Browser events are sent to `/api/observe/ingest`:

```
POST /api/observe/ingest
Content-Type: application/json
Body: browser_event (single event per beacon)
```

The ingest endpoint:
- Validates the session cookie (honest-auth)
- Stamps the event with `received_at` server timestamp
- Appends to `honest_event_log`
- Returns `204 No Content`
- Never blocks; writes asynchronously

The endpoint accepts only POST. `sendBeacon()` always sends POST.

### 8.4 Automatic Browser Events

The honest-DOM bootloader and domx emit these events automatically. No developer code required.

**`hf.browser.classify`** — emitted by the bootloader on every attribute classification
```
payload: {
    element:        String,   // CSS selector or element description
    attribute:      String,   // the h*- attribute name
    tokens:         [String], // input tokens
    manifest:       dict,     // classification result
    duration_ns:    Integer,
    request_id:     String?,  // current request context
}
```

**`hf.browser.request`** — emitted by domx on every HTMX request
```
payload: {
    method:         String,   // HTTP method
    url:            String,   // request URL
    trigger:        String,   // HTMX trigger event
    target:         String,   // HTMX swap target selector
    manifest_keys:  [String], // keys collected from DOM state
    request_id:     String,   // X-Request-ID sent with request
}
```

**`hf.browser.response`** — emitted by domx when HTMX response arrives
```
payload: {
    request_id:     String,   // joins to hf.browser.request and server events
    status:         Integer,  // HTTP status code
    swap_target:    String,   // element swapped into
    duration_ms:    Integer,  // round-trip time
}
```

**`hf.dom.changed`** — emitted by domx's MutationObserver when manifest state changes
```
payload: {
    changed_keys:   [String], // which manifest slots changed
    from:           dict,     // previous values for changed keys
    to:             dict,     // new values for changed keys
    request_id:     String?,  // current request context if within one
}
```

### 8.5 request_id Threading

The `request_id` is the join key between browser and server events.

**Server to browser:** The server sets `X-Request-ID` on every response. `@catch_at_boundary` generates the ID; the response middleware echoes it as a response header.

**Browser tracking:** domx reads `X-Request-ID` from every HTMX response header and stores it as `currentRequestId`. All browser events emitted after a response carry that `request_id` until the next response arrives.

**Resulting trace:** For any given user interaction, the complete event sequence — from DOM state change through HTMX request through server chain execution through response through DOM update — is joinable by a single `request_id`.

### 8.6 Full Unified Trace Example

A user changes a filter and the table refreshes:

```
timestamp              source   event_type              key fields
─────────────────────────────────────────────────────────────────────────────
14:23:07.001 browser  hf.dom.changed          filters: [] → ["active"]
14:23:07.003 browser  hf.browser.request      POST /api/items  req=req_abc
14:23:07.004 server   hf.classify.completed   tokens:3 rejected:0
14:23:07.005 server   hf.chain.started        create_items_query
14:23:07.006 server   hf.link.executed        validate_filters  ok  0.8ms
14:23:07.007 server   hf.link.executed        build_query       ok  0.4ms
14:23:07.008 server   hf.persist.query        SELECT items      12ms  rows:47
14:23:07.021 server   hf.link.executed        format_response   ok  0.3ms
14:23:07.022 server   hf.chain.completed      ok  16ms
14:23:07.023 server   hf.request.canonical    POST /api/items 200  16ms  req=req_abc
14:23:07.166 browser  hf.browser.response     200  163ms  req=req_abc
14:23:07.168 browser  hf.dom.changed          #content-area innerHTML swapped
14:23:07.171 browser  hf.browser.classify     hf-format on 12 new elements
```

One log. One `request_id`. No print statements anywhere.

---

## 8b. Threshold Projections and Feedback Loops

### 8b.1 The Principle

Because instrumentation is automatic and every event lands in the same log, an honest-framework application can observe its own health and respond to it. Detection, notification, approval, and remediation are all built from framework primitives. No external monitoring tool. No custom glue code. No ops team required for the common cases.

The mechanism: a **threshold projection** watches a projection value and fires a `send()` to honest-alerts when a declared threshold is crossed. The developer declares the threshold, the metric, the recipient, and optionally a remediation chain. The framework wires the rest.

### 8b.2 ThresholdProjection Schema

```python
ThresholdProjection = {
    "projection_id":   String,        # unique identifier
    "metric":          String,         # which built-in metric to watch
    "condition":       ConditionSpec,  # when to fire
    "window":          String,         # time window: "1m" | "5m" | "1h" | "24h"
    "cooldown":        String,         # minimum time between firings: "5m" | "1h" etc.
    "alert": {
        "message_type": String,        # honest-alerts message type to send
        "recipient":    ActorRef,      # who receives the alert
        "dom_surface":  String?,       # "toast" | "banner" | "modal"
        "reply_options": [ReplyOption]?, # if approval or action is needed
    },
    "remediation":     String?,        # name of chain to execute on receipt of affirmative reply
    "enabled":         Boolean,        # can be toggled without redeployment
}
```

Threshold projections are stored as honest-persist records. They can be toggled, adjusted, and created by operators at runtime without code changes or redeployment.

### 8b.3 Built-in Threshold Metrics

These metric names are built into the framework and available to any threshold projection without custom projection code.

| Metric name | Source events | Description |
|---|---|---|
| `request.error_rate` | `hf.request.canonical` | Fraction of requests with `result = "err"` |
| `request.p99_duration_ns` | `hf.request.canonical` | 99th percentile request duration |
| `request.rate_per_minute` | `hf.request.canonical` | Request volume |
| `link.fault_rate` | `hf.link.executed` | Fraction of link executions faulting, per link |
| `link.p99_duration_ns` | `hf.link.executed` | 99th percentile link duration, per link |
| `persist.query.p99_duration_ns` | `hf.persist.query` | 99th percentile query duration |
| `persist.query.error_rate` | `hf.persist.query` | Fraction of queries failing |
| `persist.pool.exhaustion_rate` | `hf.persist.pool` | Rate of pool exhaustion events |
| `persist.queue.stall_count` | `hf.persist.queue_stalled` | Count of write queue stalls |
| `classify.rejection_rate` | `hf.classify.completed` | Fraction of tokens rejected at intake |
| `browser.response.p99_duration_ms` | `hf.browser.response` | 99th percentile browser round-trip |
| `honesty.mutation_count` | `hf.link.executed` | Count of manifest mutations detected |
| `honesty.nondeterminism_count` | `hf.link.executed` | Count of non-deterministic calls detected |

### 8b.4 Built-in Threshold Projections

These are shipped as defaults. All are disabled by default in development, enabled by default in production. All can be tuned or disabled via config without code changes.

```toml
[[threshold_projections]]
projection_id = "pool_exhaustion"
metric        = "persist.pool.exhaustion_rate"
condition     = { operator = "gt", value = 0.1, per = "5m" }
window        = "5m"
cooldown      = "15m"
alert.message_type = "hf.alert.pool_exhaustion"
alert.recipient    = { type = "role", id = "on_call" }
alert.dom_surface  = "banner"
enabled       = true

[[threshold_projections]]
projection_id = "high_error_rate"
metric        = "request.error_rate"
condition     = { operator = "gt", value = 0.05, per = "5m" }
window        = "5m"
cooldown      = "10m"
alert.message_type = "hf.alert.high_error_rate"
alert.recipient    = { type = "role", id = "on_call" }
alert.dom_surface  = "banner"
enabled       = true

[[threshold_projections]]
projection_id = "slow_queries"
metric        = "persist.query.p99_duration_ns"
condition     = { operator = "gt", value = 1000000000 }  # 1 second
window        = "10m"
cooldown      = "30m"
alert.message_type = "hf.alert.slow_queries"
alert.recipient    = { type = "role", id = "developer" }
enabled       = true

[[threshold_projections]]
projection_id = "honesty_violation"
metric        = "honesty.mutation_count"
condition     = { operator = "gt", value = 0 }
window        = "1m"
cooldown      = "1m"
alert.message_type = "hf.alert.honesty_violation"
alert.recipient    = { type = "role", id = "developer" }
alert.dom_surface  = "modal"  # blocking — this should never happen
enabled       = true
```

### 8b.5 Developer Extension

A developer adds a custom threshold projection in three steps:

**Step 1: Define the metric** (only if using a custom projection — built-ins need no definition)

```python
# A custom metric watching payment failure rate
custom_metric(
    name        = "payment.failure_rate",
    event_types = ["app.payment.api_called"],
    fold        = lambda state, event: {
        "total":   state["total"] + 1,
        "failed":  state["failed"] + (1 if event.payload["result"] == "failure" else 0),
        "rate":    (state["failed"] + (1 if event.payload["result"] == "failure" else 0))
                   / (state["total"] + 1),
    },
    value       = lambda state: state["rate"],
    initial_state = { "total": 0, "failed": 0, "rate": 0.0 },
)
```

**Step 2: Declare the threshold** (in config, no code)

```toml
[[threshold_projections]]
projection_id  = "payment_failure_spike"
metric         = "payment.failure_rate"
condition      = { operator = "gt", value = 0.02 }  # 2% failure rate
window         = "5m"
cooldown       = "10m"
alert.message_type  = "app.alert.payment_failure"
alert.recipient     = { type = "role", id = "payments_team" }
alert.dom_surface   = "banner"
alert.reply_options = [
    { option_id = "acknowledge", label_id = "alerts.acknowledge", style = "primary" },
    { option_id = "escalate",    label_id = "alerts.escalate",    style = "danger" },
]
remediation    = "investigate_payment_failures"  # chain to run on escalate reply
enabled        = true
```

**Step 3: Done.** The framework wires the projection to the threshold check to the alert to the optional remediation chain. No middleware. No cron job. No external alerting system.

### 8b.6 The Feedback Loop

For threshold projections with a `remediation` chain, the full loop is:

```
event log
  → threshold projection crosses condition
    → honest-alerts send() to recipient
      → recipient receives message on DOM surface / email / SMS
        → recipient replies via reply_options
          → if affirmative reply: remediation chain executes
            → chain writes new config record to honest-persist
              → application reads new config on next request
                → condition resolves
                  → threshold projection drops below threshold
                    → alert auto-expires via TerminationSpec
```

Every step uses a framework primitive. The developer declares the loop; the framework executes it.

### 8b.7 The Honesty Violation Loop

The mutation detection feedback loop deserves special mention because no other framework can implement it. A mutation — a link that modified its input manifest — is detected by the `@link` decorator and recorded as `hf.link.executed.mutations > 0`. The threshold projection fires immediately. The developer receives a modal alert with the link name, chain name, and the diff between the input and output manifests. There is no cooldown: every mutation is an error. The alert does not expire until the developer acknowledges it and deploys a fix.

This is a zero-tolerance feedback loop for architectural dishonesty, delivered automatically, requiring no developer instrumentation.

---

## 8c. External Source Ingestion

Sections 8 (browser) and earlier describe how events enter the log from the three collection layers of a single honest-framework application: frontend, middleware, database. This section covers the fourth class of source: **external systems** that are not instrumented by honest-observe — third-party SaaS webhooks (Stripe, Salesforce, ServiceNow), partner systems, federated honest-framework deployments, legacy services, IoT devices.

One log remains the source of truth. External events reach it through a declared ingestion contract: translator, clock reconciliation, identity binding.

### 8c.1 The Translator Pattern

Each external source has exactly one translator: a pure function that converts the source's native event into the canonical envelope (section 2), or returns a rejection.

```
translate_<source>(raw_event) → canonical_event | rejection
```

The translator is the only place where source-specific knowledge lives. Everything downstream sees canonical envelopes.

```python
def translate_stripe_payment(raw: dict) -> dict | Rejection:
    if not recognize_stripe_payment(raw):
        return reject("unrecognized_stripe_shape", raw)
    return {
        "event_id":       uuid_v7(),
        "event_type":     "payment.cleared",
        "event_version":  "1.0",
        "timestamp":      raw["created"],  # stripe timestamp
        "sequence":       0,               # filled in on append
        "aggregate_type": "payment",
        "aggregate_id":   resolve_identity(raw["customer"], "stripe"),
        "payload": {
            "amount":   raw["amount"],
            "currency": raw["currency"],
        },
        "auth": { "caller_id": "stripe:webhook" },
        "meta": {
            "source":         "stripe",
            "external_id":    raw["id"],
            "source_hlc":     hlc_now(),
            "translator_version": "1.0",
        },
    }
```

Translators are pure. Test with captured payload fixtures, assert on canonical output. No webhook mocking.

### 8c.2 Hybrid Logical Clocks

`timestamp` + `sequence` (section 2.1) provides total order within one aggregate on one clock. External sources do not share a clock. Network delays, clock skew, and retries mean that a strict wall-clock sort is not a causal order.

Hybrid Logical Clocks (HLC) give a total order that respects causality without requiring synchronized time.

```
hlc = {
    physical: Integer,   # milliseconds since epoch, local best guess
    logical:  Integer,   # always-increasing counter for same-millisecond events
    source:   String,    # source_id tiebreaker
}
```

On send, HLC is advanced: `max(local_physical, last_seen_hlc.physical)` with the logical counter incremented when physical time did not advance. On receive, the receiver advances its local HLC against the incoming one. The result: events from the same source preserve their order, events across sources interleave by physical time, and identical physical times are broken by logical counter then source_id.

**Stored in `meta.source_hlc`.** The existing `timestamp` field is unchanged (operator wall-clock view). Projections that need causal order sort by `meta.source_hlc`.

### 8c.3 Identity Binding

The same entity has different IDs in different systems. `user-42` in your system is `cus_Nx3a9c` in Stripe, `U000123` in Salesforce, `usr_abc` in Auth0. Identity resolution is a separate concern from translation.

**Claims are events.** An identity claim is an append-only record asserting a mapping:

```
event_type: "identity.claimed"
payload: {
    canonical_id:     "user-42",
    external_system:  "stripe",
    external_id:      "cus_Nx3a9c",
    evidence:         "webhook_signature_verified",
    asserted_by:      "system:stripe_translator",
}
```

**Bindings are a projection of claims.** The `identity_binding` projection reduces all `identity.claimed` events into a lookup table: `(external_system, external_id) → canonical_id`. Conflicts (two claims, different canonical IDs, same external ID) are written to the rejection log and require human adjudication via a new claim with higher evidence.

```python
def resolve_identity(external_id, source, bindings) -> str | None:
    return bindings.get((source, external_id))
```

When a translator encounters an unresolvable external ID, it emits `identity.unknown` and returns a rejection. A background link attempts resolution (by querying the source's API or by human review) and emits new claims.

### 8c.4 External Ingest Endpoint

Per-source ingest endpoint, distinct from the browser endpoint at `/api/observe/ingest`:

```
POST /api/observe/ingest/<source_id>
Content-Type: application/json
Authorization: <source-specific auth, e.g. HMAC signature>
Body: raw_event (source-native format)
```

The endpoint:
1. Validates source-specific auth (HMAC, shared secret, mTLS — configured per source).
2. Stamps `received_at` with server wall-clock time.
3. Invokes the registered translator for `<source_id>`.
4. If translation succeeds, appends the canonical event to `honest_event_log` with `meta.source = <source_id>`.
5. If translation returns a rejection, appends to `honest_rejection_log` with the raw event and rejection reason.
6. Returns `204 No Content` on success, `400` on rejection (for synchronous sources that care), `401` on auth failure.
7. Is idempotent by `(source_id, external_id)` — duplicate deliveries are deduped, not re-translated.

### 8c.5 Conflicts and Rejections

Rejections are data, not exceptions (core Honest Code principle). A dedicated `honest_rejection_log` captures every raw event that failed translation or identity resolution:

```
rejection = {
    rejection_id:     uuid_v7(),
    received_at:      timestamp,
    source:           String,
    reason_code:      String,    # "unrecognized_shape", "identity_unknown", "conflict", "auth_failed"
    reason_detail:    dict,
    raw_event:        dict,      # preserved verbatim for forensics
    translator_version: String,
}
```

The rejection log is a first-class projection target. A developer fixing a schema drift queries it: "show me every Stripe rejection in the last 24 hours." They patch the translator, bump its version, and replay the rejections through the new translator. Successful re-translations append to the event log with the new `translator_version`; the original rejections remain for audit.

### 8c.6 Translator Versioning

Translators evolve when source schemas change. Versioning is explicit:

```
translator_registry = {
    "stripe": {
        "1.0": translate_stripe_payment_v1,
        "1.1": translate_stripe_payment_v1_1,   # added fee fields
        "2.0": translate_stripe_payment_v2,     # breaking: amount split into net/fee
    },
}
```

**On ingest:** the current default version is applied; the version is recorded in `meta.translator_version`.

**On replay:** a new translator can be applied retroactively to historical raw events if they were captured (which they are, in the rejection log or a dedicated `raw_ingestion_log` for sources configured to retain raw). Replay produces new canonical events with the new `translator_version` and a `meta.supersedes: <old_event_id>` link. The old events are not deleted (the log is immutable); projections are configured to filter out superseded events or include both depending on the question.

### 8c.7 What Section 8c Adds to the Log Model

Section 2's envelope is unchanged. Section 8c adds three conventions inside `meta`:

- `source` — external source identifier, or absent for internal events
- `source_hlc` — hybrid logical clock for causal ordering across sources
- `translator_version` — version of the translator that produced this event

And one new append-only log alongside `honest_event_log`:

- `honest_rejection_log` — raw events that could not be translated, with reason

The rest of the framework — emit, projections, threshold projections, OTel export — operates on canonical events and does not need to know whether an event originated internally or from an external source. That is the whole point of translation.

---

## 9. Development Tools

These tools read the event log and present it in forms useful during development. They are projections. They do not add instrumentation; they consume what the framework already emits.

### 9.1 The Principle: Every Function Is a Print Statement

In a conventional application, a developer writes `print(f"validate_email called with {manifest}")` because there is no other way to see what a function received. In an honest-framework application, the `@link` decorator already recorded that fact as `hf.link.executed` with the input manifest. The print statement has nothing to say that the event log does not already know.

Development tooling makes this visible. The developer does not change what they emit — the framework emits everything automatically. The developer only chooses how to read it.

### 9.2 honest-observe tail

Streams the event log to the terminal in real time, in structured key=value format. This is the development replacement for a log tail.

```bash
honest-observe tail
honest-observe tail --source server
honest-observe tail --source browser
honest-observe tail --event hf.link.executed
honest-observe tail --chain create_user_pipeline
honest-observe tail --request req_abc123
honest-observe tail --since 5m
```

**Output format:**

```
14:23:07.006 server  hf.link.executed  link=validate_filters chain=fetch_items result=ok duration=0.8ms
14:23:07.007 server  hf.link.executed  link=build_query chain=fetch_items result=ok duration=0.4ms
14:23:07.008 server  hf.persist.query  table=items op=select rows=47 duration=12ms
14:23:07.021 server  hf.link.executed  link=format_response chain=fetch_items result=ok duration=0.3ms
14:23:07.022 server  hf.chain.completed  chain=fetch_items result=ok duration=16ms
14:23:07.023 server  hf.request.canonical  method=POST path=/api/items status=200 duration=16ms req=req_abc
14:23:07.166 browser hf.browser.response  status=200 duration=163ms req=req_abc
14:23:07.168 browser hf.dom.changed  keys=[#content-area]
```

This is the Stripe canonical log line insight applied: every meaningful thing that happened, in order, as a stream. No configuration. No log levels. No handlers. The developer runs one command and sees everything.

### 9.3 honest-observe inspect

Renders the complete execution tree for one request: browser and server events interleaved in timestamp order, formatted as a readable trace.

```bash
honest-observe inspect req_abc123
```

**Output:**

```
Request: req_abc123
POST /api/items → 200  total: 166ms

BROWSER
  14:23:07.001  dom.changed       filters [] → ["active"]             0.1ms
  14:23:07.003  browser.request   POST /api/items                      —

SERVER
  14:23:07.004  classify          3 tokens, 0 rejected                 0.2ms
  14:23:07.005  chain.started     fetch_items  3 links
  14:23:07.006    link            validate_filters          ok          0.8ms
  14:23:07.007    link            build_query               ok          0.4ms
  14:23:07.008    persist.query   SELECT items WHERE ...    47 rows     12.0ms
  14:23:07.021    link            format_response           ok          0.3ms
  14:23:07.022  chain.completed   fetch_items               ok          16.0ms
  14:23:07.023  canonical         POST /api/items 200                  —

BROWSER
  14:23:07.166  browser.response  200  #content-area swapped           163ms
  14:23:07.168  dom.changed       #content-area innerHTML
  14:23:07.171  classify          12 elements                          1.1ms

Total: 166ms  (server: 16ms  network: 147ms  browser: 3ms)
```

This is the development replacement for attaching a debugger or scattering print statements to understand a specific request.

### 9.4 honest-observe query

Runs a named projection against the event log and prints the result. Useful for operational queries during incidents.

```bash
# Which links are slowest in the last hour?
honest-observe query link-latency --since 1h

# Which users hit faults today?
honest-observe query user-faults --since 24h

# How many requests per minute for the last 30 minutes?
honest-observe query request-rate --since 30m --bucket 1m
```

Projections are defined in `honest-observe.toml` or in application code. `honest-observe query` resolves projection names from the registry and runs them.

### 9.5 Development Mode

In development mode (`environment = "development"` in config), honest-observe activates additional behavior:

- `tail` streams automatically to the terminal without requiring an explicit command
- `hf.link.executed` payloads include the full input and output manifest values (production omits values for privacy)
- `hf.app.error` payloads include full tracebacks
- `hf.classify.completed` events are enabled (production default: disabled, high volume)
- Browser events include full manifest contents

Development mode is controlled by config, not by code. No `if DEBUG:` guards anywhere.

### 9.6 Configuration

```toml
[development]
enabled    = true         # activates development mode
auto_tail  = true         # stream to terminal automatically
manifests  = true         # include manifest contents in link events
tracebacks = true         # include tracebacks in error events
```

---

## 10. The Event Log in honest-persist

The event log is a table in honest-persist with append-only semantics. No UPDATE or DELETE is ever issued against this table.

```sql
CREATE TABLE honest_event_log (
    event_id        TEXT        PRIMARY KEY,
    event_type      TEXT        NOT NULL,
    event_version   TEXT        NOT NULL,
    timestamp       TEXT        NOT NULL,
    sequence        INTEGER     NOT NULL,
    aggregate_type  TEXT        NOT NULL,
    aggregate_id    TEXT        NOT NULL,
    payload         TEXT        NOT NULL,   -- JSON
    auth            TEXT,                   -- JSON, nullable
    meta            TEXT,                   -- JSON, nullable

    -- Indexes for common projection patterns
    INDEX idx_event_type   (event_type),
    INDEX idx_aggregate    (aggregate_type, aggregate_id),
    INDEX idx_timestamp    (timestamp),
    INDEX idx_sequence     (aggregate_id, sequence),
)
```

honest-persist enforces append-only semantics by rejecting UPDATE and DELETE statements against this table. This is declared in the table's honest-persist manifest:

```python
event_log_manifest = table_manifest(
    table      = "honest_event_log",
    append_only = True,     # UPDATE and DELETE produce a server fault
    schema     = event_envelope_schema,
)
```

---

## 11. Configuration

```toml
# honest-observe.toml

[event_log]
table = "honest_event_log"         # honest-persist table name
db_id = "primary"                  # which database
retention_days = 365               # events older than this may be archived

[auth]
provider = "honest-auth"           # "honest-auth" | "custom" | "none"
# If "custom", declare your field names:
# fields = ["user_id", "session_token", "tenant_id"]

[framework_events]
chain_events    = true    # emit hf.chain.* events
link_events     = true    # emit hf.link.* events
persist_events  = true    # emit hf.persist.query events (emitted from inside honest-persist)
migration_events = true   # emit hf.persist.migration events
pool_events     = true    # emit hf.persist.pool events
state_events    = true    # emit hf.state.* events
classify_events = false   # emit hf.classify.* events (high volume, off by default)

[otel]
enabled     = false                # false until exporter is configured
service     = "my-application"
environment = "production"
# Exporter configured in application code via install_otel_exporter()

[snapshots]
enabled           = true
default_interval  = 1000           # snapshot every N events
storage_table     = "honest_projection_snapshots"
```

---

## 12. Conformance

### 12.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | `emit()` correctly appends events; framework chain and link events auto-emitted; canonical request event emitted by `@catch_at_boundary` |
| **Full** | Core + state machine events + persist events + startup/shutdown events + projection interface + snapshot projections |
| **Browser** | Browser event envelope; `sendBeacon` to `/api/observe/ingest`; `request_id` threading; all four automatic browser event types |
| **Complete** | Full + Browser + OTel exporter + development tools (`tail`, `inspect`) + honest-framework semantic conventions |

### 12.2 Conformance Suite

The conformance suite lives at `honest/honest-observe-conformance/suite.json`. Test cases cover:

- `emit()` produces a valid event envelope with all required fields
- `emit()` returns `ok` with `event_id` on success
- `emit()` returns `err` with `emit_failed` on persist failure
- Framework events are auto-emitted with correct payloads
- `hf.request.canonical` is emitted last for every request, contains correct link sequence
- `hf.app.started` emitted at startup with correct chain/link/vocab counts
- Projection fold produces correct derived state from a fixed event sequence
- Snapshot projection resumes from snapshot correctly
- Auth partition is preserved verbatim from context
- Browser event envelope contains all required fields
- `/api/observe/ingest` appends browser events to the same log
- `request_id` in browser events matches server canonical event
- OTel span attributes include all `hf.*` semantic conventions
- `tail` output includes browser and server events interleaved by timestamp
- `inspect` output groups events by source with correct timing breakdown
