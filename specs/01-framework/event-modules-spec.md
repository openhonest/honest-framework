# Honest Framework: Event Modules

Four new modules, all built on the **honest-observe event log** (see `specs/02-code-quality/honest-observe-architecture.md`). honest-observe is the foundation: append-only immutable log, canonical event envelope, emit/projection API, browser and external source ingestion. These modules are **vocabularies + projections** layered on top.

- **honest-publish** — pub-sub, fan-out delivery
- **honest-queue** — work queue, competing consumers
- **honest-itil** — ITIL records as derived views (projections) over the log
- **honest-forecast** — capacity planning as projections + pluggable forecasters

No new storage. No new log semantics. Each module adds a recognizer vocabulary for its event types and a set of projections that reduce the log into the shapes that module cares about. Cross-system ingestion (translators, HLC, identity binding) is specified in honest-observe §8c, not here.

---

## honest-publish

Pub-sub. Fan-out delivery. Every subscriber sees every message matching its topic recognizer.

### Shape

```
message   :: TypedDict   # wire format, recognizer-validated
topic     :: recognizer  # String → Boolean, selects which messages a handler sees
handler   :: link        # pure function: message → list[effect] | fault
subscriber:: {topic, handler, binding}
broker    :: parameter   # I/O boundary, passed in, never global
```

### Core verbs

- `publish(broker, message)` — publish one message to all matching subscribers
- `subscribe(broker, topic, handler)` — register handler for messages matching topic recognizer
- `dispatch(subscribers, message)` — pure function, returns list of (handler, message) pairs to run
- `drain(broker)` — consume until empty (test helper)

Distinct from honest-observe's `emit()` (write one event to the canonical log). A handler typically does both: it observes inputs and outputs via `emit()`, and it publishes downstream messages via `publish()`.

### Canonical example

```python
# Handlers are pure. Broker is a parameter.
def on_user_created(message: UserCreated) -> list[Effect]:
    return [Effect("email.queue", WelcomeEmail(to=message["email"]))]

HANDLERS = {
    "user.created":  on_user_created,
    "order.placed":  on_order_placed,
    "payment.cleared": on_payment_cleared,
}

# Dispatch is dict-lookup (P01). Not a visitor pattern.
def dispatch(handlers, message):
    handler = handlers.get(message["type"])
    return handler(message) if handler else []

# Broker is injected (P13 — no globals).
def run_subscriber(broker, handlers):
    for message in broker.consume():
        effects = dispatch(handlers, message)
        for effect in effects:
            publish(broker, effect)
```

### What honest-publish does NOT have

- No base `Handler` class. Handlers are functions.
- No event-listener inheritance. Recognizers compose.
- No singleton bus. Broker is a parameter.
- No mock broker in tests. Test `dispatch(handlers, message)` directly.
- No try/except sprawl in handlers. Typed faults at the boundary (P08).

---

## honest-queue

Work queue. Competing consumers. Each message is delivered to exactly one worker. Retry and DLQ are first-class.

### Shape

```
task       :: TypedDict   # the unit of work
worker     :: link        # pure function: task → result | fault
outcome    :: {result | retry | dead_letter}
policy     :: TypedDict   # max_attempts, backoff, dead_letter_topic
queue      :: parameter   # I/O boundary
```

### Core verbs

- `enqueue(queue, task)` — submit work
- `claim(queue, worker_id)` — lease a task (visibility timeout)
- `complete(queue, task_id, result)` — ack
- `fail(queue, task_id, fault)` — nack, policy decides retry vs DLQ
- `decide(policy, attempt, fault) → outcome` — pure function, testable

### The retry decision is a pure function

```python
def decide(policy: Policy, attempt: int, fault: Fault) -> Outcome:
    if fault["type"] == "permanent":
        return Outcome("dead_letter", fault)
    if attempt >= policy["max_attempts"]:
        return Outcome("dead_letter", fault)
    delay = policy["backoff_base"] * (2 ** attempt)
    return Outcome("retry", delay)

# Test without a real queue.
assert decide(P, 0, transient_fault) == Outcome("retry", 1.0)
assert decide(P, 5, transient_fault) == Outcome("dead_letter", ...)
assert decide(P, 0, permanent_fault) == Outcome("dead_letter", ...)
```

### publish vs queue — when to use which

| Need                              | Module         |
|-----------------------------------|----------------|
| Every subscriber reacts           | honest-publish |
| Exactly one worker processes      | honest-queue   |
| Broadcast state change            | honest-publish |
| Distribute batch work             | honest-queue   |
| At-least-once, no ordering        | honest-publish |
| At-least-once with retry + DLQ    | honest-queue   |

They share the pure-handler shape. They differ on delivery semantics. One module would need mode flags that blur the boundary, which is why they stay separate.

---

## honest-itil

ITIL records are **derived views** over the event log. No separate CMDB, no ticket-vs-reality drift. The ledger is truth, the ITIL record is a reduction.

### The insight

Traditional ITIL tools are parallel bookkeeping. Engineers do the real work, then a human (or a flimsy sync job) updates the ticket. The tools diverge from reality within hours.

In Honest Code, `honest-observe` already records every event. Every deploy emits `change.applied`. Every alert emits `incident.opened`. Every service registration emits `service.declared`. ITIL records don't need to be maintained — they need to be queried.

### Canonical vocabulary

Recognizers over the event log:

```
incident.opened   :: {type, severity, service_id, opened_at, signature}
incident.resolved :: {type, incident_id, resolved_at, resolution}
change.requested  :: {type, requested_by, target_service, diff, risk}
change.approved   :: {type, change_id, approver, approved_at}
change.applied    :: {type, change_id, applied_at, deploy_sha, rollback_plan}
change.rolled_back:: {type, change_id, rolled_back_at, reason}
service.declared  :: {type, service_id, owner, depends_on, sla}
service.deprecated:: {type, service_id, deprecated_at, successor}
request.submitted :: {type, requester, catalog_item_id, params}
request.fulfilled :: {type, request_id, fulfilled_at, outcome}
sla.breached      :: {type, service_id, window, metric, threshold, actual}
```

Every event is a TypedDict. Every event is recognizer-classified. Every ITIL view is a pure reduction.

### The five derived views

**1. Incident register (open + recent closed)**

```python
def incident_register(events, window):
    opens = filter(recognize_incident_opened, events)
    resolves = filter(recognize_incident_resolved, events)
    return reduce_open_incidents(opens, resolves, window)
```

**2. CMDB (current topology)**

```python
def cmdb(events, as_of):
    declares = filter(recognize_service_declared, events, before=as_of)
    deprecates = filter(recognize_service_deprecated, events, before=as_of)
    return reduce_topology(declares, deprecates)
```

CMDB-as-of-any-point-in-time is free. Historical queries are `cmdb(events, last_tuesday)`.

**3. Change log (audit trail)**

Already exists. It IS the event log filtered by `change.*`. No separate change records.

**4. Problem register (clustered incidents)**

```python
def problem_register(events, clustering_recognizer):
    incidents = filter(recognize_incident_opened, events)
    clusters = group_by(incidents, signature_recognizer)
    return [{"problem_id": hash(sig), "incidents": is_} for sig, is_ in clusters]
```

A problem is a recurring signature across incidents. Pure groupby over the log. No human maintains the problem-to-incident links.

**5. SLA compliance**

```python
def sla_compliance(events, service_id, window) -> Compliance:
    # Pure function. Input: event log. Output: {availability, p99, breach_count}.
    service_events = filter(by_service(service_id), events, window)
    return reduce_sla_metrics(service_events)
```

Breach detection runs on every new event. Produces `sla.breached` events. Which are themselves input to incident recognition. The feedback loop is data, not orchestration.

### Service catalog

The catalog IS the manifest of registered components (already maintained by the component runtime). Adding ITIL metadata is a binding: each `service.declared` event carries catalog fields (owner, SLA, support tier). The catalog view is a reduction over these events.

### Request fulfillment

A catalog request (provision a database, grant access, etc.) is an event chain:

```
request.submitted → approval link → change.requested → change.applied → request.fulfilled
```

Every step is an event. Every handler is a pure function + one I/O effect at the end. The "workflow" is just the chain. No BPMN, no state machine library, no orchestrator service.

### What honest-itil does NOT do

- **No separate storage.** The ledger IS the CMDB, incident DB, change DB.
- **No sync jobs** between reality and records. Records are queries over reality.
- **No ticket lifecycle state machine.** States are derived from which events have occurred.
- **No manual problem linking.** Clustering is a recognizer over incident signatures.
- **No SLA dashboards that disagree with metrics.** The SLA view IS the metric reduction.

### When ServiceNow / Jira SM must be canonical

Some orgs cannot accept "the log is the system of record" — auditors want ServiceNow. The honest move is still the same architecture, with one addition: a **one-way publisher** link that emits canonical events to ServiceNow. ServiceNow becomes a downstream subscriber, never a source of truth. If auditors want ServiceNow to also be a source, treat it as an external event source and merge via translator (next section). Do not make the internal log depend on ServiceNow's state.

---

## honest-forecast

Capacity planning as pure reductions over the event log, with pluggable forecasters. Same foundation as honest-itil, different vocabulary.

### The insight

Capacity planning tools (Datadog Forecasts, AWS Auto Scaling, custom dashboards) maintain their own time-series databases, their own aggregations, their own anomaly models. They diverge from reality the same way ITIL tools do. If the event log already carries `task.enqueued`, `task.completed`, `resource.sampled`, `queue.depth.sampled`, then capacity views are reductions, forecasts are pure functions over those reductions, and scaling recommendations emit as events that honest-itil handles as change requests.

### Canonical vocabulary

```
resource.sampled     :: {type, service_id, metric, value, sampled_at}
queue.depth.sampled  :: {type, queue_id, depth, sampled_at}
throughput.observed  :: {type, service_id, rate, window, observed_at}
latency.observed     :: {type, service_id, p50, p95, p99, window}
capacity.provisioned :: {type, service_id, units, provisioned_at}
capacity.projected   :: {type, service_id, horizon, method, projection}
scale.recommended    :: {type, service_id, direction, delta, reason}
saturation.warning   :: {type, service_id, metric, threshold, actual, eta}
```

Every sample is an event. Every projection is an event. Scaling recommendations are events. The forecaster is a pure function over historical events; its output is an event. No separate time-series database required at the semantic layer (the storage layer may still be columnar underneath, but that is `honest-persist`'s concern).

### Core verbs

- `measure(events, window, metric) → measurement` — pure reduction over windowed events
- `project(history, horizon, method) → projection` — forecaster link, method is pluggable
- `size(projection, sla) → capacity` — pure function: minimum units to hold SLA
- `recommend(current, projection, sla) → Scale` — pure function: scale up, down, or hold

### Pluggable forecasters

The framework ships the data shape. Each language ships idiomatic forecasters as links that implement the `project` signature.

```python
# Python — pluggable method
def project(history, horizon, method="ewma"):
    forecasters = {
        "linear":     linear_projection,
        "ewma":       ewma_projection,
        "holt_winters": holt_winters_projection,
        "seasonal":   seasonal_projection,
    }
    return forecasters[method](history, horizon)
```

Each forecaster is a pure function. Test with fixed historical arrays, assert on projection values. No mocks.

### Segmented forecasts for free

Forecasts are recognizer-composable. If you can recognize `business_hours`, `month_end`, `deploy_window`, `holiday`, you get segmented forecasts without new code:

```python
# Separate projection per segment.
for segment, recognizer in segments.items():
    history = filter(recognizer, events)
    projections[segment] = project(history, horizon)
```

Most capacity tools hardcode daily/weekly/monthly seasonality. Honest Code makes seasonality another vocabulary. Custom business rhythms (quarter-end, promotional windows, maintenance windows) are just recognizers you add.

### The closed loop

```
event log
  │
  ├─ measure(events, window) ──► measurement events
  │                                 │
  │                                 ▼
  │                           project(history) ──► capacity.projected events
  │                                                    │
  │                                                    ▼
  │                                          recommend(current, proj, sla)
  │                                                    │
  │                                                    ▼
  │                                          scale.recommended event
  │                                                    │
  │                                                    ▼
  │                                     honest-itil: change.requested
  │                                                    │
  │                                                    ▼
  │                                     approval link → change.applied
  │                                                    │
  ▼                                                    ▼
capacity.provisioned ◄─────────────────────── (feedback)
```

The loop is data. No orchestrator service. No cron job stitching things together. Each arrow is a handler subscribed to the appropriate recognizer on the event stream.

### What honest-forecast does NOT ship

- **No statistical models.** Implementations plug in scipy/statsmodels (Python), simple-statistics (JS), Nx (Elixir), etc. The spec defines the signature, not the math.
- **No separate time-series store.** The log is the source. Downsampling and retention are concerns of `honest-persist`.
- **No dashboards.** Views are rendered by components that query the reductions.
- **No alert rules engine.** Saturation detection is a recognizer. Alerts are events.

### Tradeoffs

Serious forecasting needs confidence intervals, anomaly detection, and quantile regression. The framework won't ship those; it defines the data shape and delegates to language-native libraries. This is the same pattern as honest-type: a spec, not a runtime.

---

## Cross-system ingestion

Specified in **honest-observe §8c (External Source Ingestion)**. Translator pattern, hybrid logical clocks, identity binding, the per-source ingest endpoint, the rejection log, and translator versioning all live there. All four modules in this spec operate on canonical events; they do not need to know whether an event came from an internal boundary, a browser beacon, or an external source webhook. That is the whole point of honest-observe's ingestion model.

Key takeaways relevant to these modules:

- **Canonical envelope.** Every event seen by publish/queue/itil/forecast is already in the honest-observe envelope (section 2).
- **HLC ordering.** Events carry `meta.source_hlc` when they originated externally. Projections that need causal order sort on it; projections that only care about one system's view sort on `timestamp` + `sequence`.
- **Identity already resolved.** By the time an event reaches these modules, external IDs have been mapped to canonical IDs through the identity-binding projection.
- **Rejections are data.** A translator rejection never reaches these modules — it is written to `honest_rejection_log` and handled by honest-itil as a different event class if it matters operationally.

---

## How the four modules interact

```
honest-observe event log  (the foundation, see honest-observe spec)
  │
  ├──►  honest-itil       projections: incident register, CMDB, change log,
  │                                     problem register, SLA compliance
  │
  ├──►  honest-forecast   projections: measurements, projections, recommendations
  │                                     closed loop → scale.recommended events
  │
  ├──►  honest-publish       delivery:    fan-out to matching subscribers
  │
  └──►  honest-queue      delivery:    competing consumers, retry, DLQ
```

One log. Two delivery modes (fan-out, competing consumers). N projection vocabularies (ITIL records, capacity views, and anything else — audit, meter, analytics, cost, detect, consent, lineage, rate, runbook). Every boundary typed by recognizers. Every handler a pure function. The broker, the queue, the log — all parameters.

---

## Open questions

1. **HLC implementation:** roll our own, or use an existing library per language? Rolling our own is ~30 lines and avoids a dependency for a core abstraction. (Affects honest-observe §8c.2 as well.)
2. **Recognizer compilation for projection queries at scale:** if the log is 100M events, view queries need indexes. Where do recognizers get compiled into SQL WHERE clauses? Probably in `honest-persist`, as a pushdown optimization on recognizer composition.
3. **Schema evolution for canonical events:** translator versioning (honest-observe §8c.6) handles external events. Internal event schema changes need a parallel mechanism — versioned recognizers? Migration links that translate v1 events to v2 on read?
4. **Recognizer subscription model.** honest-publish uses recognizer predicates as topics. At scale, do we index subscribers by recognizer for O(1) dispatch, or accept O(n) scan for simplicity? Probably tiered: exact-type-match index + predicate-scan fallback.
