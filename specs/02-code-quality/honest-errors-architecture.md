# honest-errors: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** June 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-errors is the **error-policy leaf** of the Honest Framework. It normalizes raw failure payloads (browser-JavaScript errors, server-side exceptions) into one canonical `ExceptionReport`, decides what should *happen* to a report as a function of the environment, and throttles repeat notifications. It performs no I/O. It is composed by two modules that do: honest-observe (which records the report as an event) and honest-alerts (whose supervisor delivers any notification the policy calls for).

honest-errors exists as its own module, rather than being folded into observe or alerts, for one reason: error handling is **common to both**. observe needs the capture-and-normalize half; alerts needs the decide-and-throttle half; both share the `ExceptionReport` type and the rate-limiter. Splitting the capability across the two consumers would either duplicate that shared core or force one consumer to depend on the other. A shared leaf composed by both is the DRY, composition-first answer — the module-level form of `pipe(...)`.

### 1.1 The abstract requirement

> *A failure becomes one canonical report; what happens to that report is a pure function of the environment and the report's own content; and repeat notifications are suppressed by a deterministic throttle. None of this performs I/O.*

honest-errors turns the question "what do we do when something breaks?" into data: a normalized report, a list of named behaviors, and a throttle decision. The acts of logging and sending are left to the modules that own those boundaries.

### 1.2 Which bug categories this eliminates (poka-yoke)

| Decision | Bug category made impossible |
|---|---|
| One `ExceptionReport`, two normalizers | Divergent error shapes between the JS and server paths; downstream code branching on source |
| Environment → behaviors as a dispatch table | `if env == "production"` ladders drifting out of sync; an environment silently getting no policy |
| Throttle decision is data (`RateLimitDecision`), never an exception | Notification storms, or a throttle that swallows errors as a side effect instead of reporting suppression |
| Bounded vocabularies (severity, environment, behavior, reason) as frozensets | Stringly-typed states that cannot be enumerated, and therefore cannot be exhaustively tested or statically checked |
| No I/O in the module | Hidden environment reads / clock reads / sends buried inside "pure" policy functions — the thing that makes error handling untestable |

### 1.3 Relationship to honest-observe and honest-alerts

honest-errors is a leaf; both of these compose it. It depends on neither.

| Consumer | What it composes from honest-errors |
|---|---|
| **honest-observe** | The normalizers. A raw failure payload is classified into an `ExceptionReport`, which observe records as an error event in its log (observe owns `@catch_at_boundary` and the event envelope; honest-errors owns the *shape* of the report). |
| **honest-alerts** | The behavior table and the rate-limiter. The supervisor (honest-alerts §1.1) reads `behaviors_for(environment)` to decide whether a report warrants a notification, and `check_rate_limit(...)` to decide whether to suppress a repeat. An `email` behavior becomes an alerts `Message` routed by the `AlertRoute` table. |

### 1.4 What honest-errors covers

- The payload IR: `JSErrorPayload`, `PythonExceptionPayload`, and the canonical `ExceptionReport` (all TypedDicts).
- The bounded vocabularies: severities, environments, behavior names, suppression reasons.
- Normalization: `classify_js_payload`, `classify_py_payload` → `Result[ExceptionReport]`.
- Behavior policy: the environment → behaviors dispatch table and `behaviors_for`.
- The rate-limiter: `dedup_key`, `new_state`, `check_rate_limit` (pure, state-threaded, injected clock).
- The email-body formatter (a pure report → text rendering, for use by an `email` behavior).

### 1.5 What honest-errors does not cover

- **Recording the report.** honest-observe writes it to the event log. honest-errors never logs.
- **Sending a notification.** honest-alerts' supervisor delivers it over a channel. honest-errors never sends.
- **Reading the environment or the clock.** These are passed in as arguments by the composing boundary. honest-errors never calls `os.getenv` or reads a wall clock inside a policy function.
- **Capturing the exception.** The boundary (`@catch_at_boundary`, an HTTP error handler, a browser hook) catches; honest-errors only normalizes what it is handed.

---

## 2. The Report IR

All IR is TypedDict. No classes, no methods.

```
JSErrorPayload = {
    message, source, lineno, colno, stack, url, user_agent, timestamp: ...,
    context: dict,
}

PythonExceptionPayload = {
    exception_type, message, tb_file, tb_line, tb_function, traceback: ...,
    context: dict,
}

ExceptionReport = {
    exception_type: String,
    message:        String,
    severity:       String,    # one of SEVERITIES
    environment:    String,    # one of ENVIRONMENTS
    file:           String,
    line:           Integer,
    function:       String,
    traceback:      String,
    context:        dict,
    timestamp:      String,    # ISO-8601, supplied by the caller
}
```

The two payload shapes collapse to one report so that every downstream consumer — the observe event, the alerts notification, the email body — is source-agnostic.

### 2.1 Bounded vocabularies

```
SEVERITIES       = { debug, info, warning, error, critical }   # frozenset
ENVIRONMENTS     = { development, production, test }           # frozenset
BEHAVIOR_NAMES   = { log, email, reraise }                     # frozenset
SUPPRESS_REASONS = { rate_limit_hourly, rate_limit_dedup }     # frozenset
```

**Normative change from the prototype.** These are closed sets and must be declared as frozensets, not free `str` (the prototype documents them in comments but enforces `str`). honest-test enumerates them; honest-check treats them as discriminant sets.

---

## 3. Normalization

```
classify_js_payload(payload, environment, timestamp) -> Result[ExceptionReport]
classify_py_payload(payload, environment, timestamp) -> Result[ExceptionReport]
```

```
Result[ExceptionReport] = { "ok": ExceptionReport } | { "err": Fault }
```

**Normative change from the prototype.** `environment` and `timestamp` are **arguments**, not read inside the function from `os.getenv` / the system clock. The prototype's translators smuggle both in as hidden I/O; that is the single I/O-at-boundary violation the spec corrects. The boundary that catches the failure already knows the environment and the time; it passes them in.

Each function validates the raw payload against the required keys for its shape and returns `{ "err": Fault(code="malformed_payload", ...) }` when a required key is absent, otherwise `{ "ok": ExceptionReport }`. Severity for the Python path defaults to `error`; for the JS path it is derived from the payload (a message marked `critical` yields `critical`, else `error`) via a small predicate — not an `if` ladder that would grow per rule.

### 3.1 `should_bypass_dedup`

```
should_bypass_dedup(severity) -> Bool      # True iff severity == critical
```

A pure predicate. Critical failures are never silenced by the throttle (§5). This is the one product rule baked into the leaf, expressed as data, not control flow.

---

## 4. Behavior Policy

What should happen to a report is a list of named behaviors, looked up by environment.

```
HandlerBehavior = { name: String, order: Integer }   # name in BEHAVIOR_NAMES

BEHAVIORS_BY_ENV = {
    development: [ {log, 0}, {reraise, 1} ],
    production:  [ {log, 0}, {email,   1} ],
    test:        [ {log, 0} ],
}

behaviors_for(environment) -> list[HandlerBehavior]
```

`behaviors_for` is a pure dict lookup with a declared default (development). Adding an environment or changing a policy is editing the table, never editing control flow. The list is *data*: the composing boundary interprets each behavior — `log` is handed to honest-observe, `email` to honest-alerts, `reraise` to the boundary itself. honest-errors does not execute behaviors; it declares them.

**Normative change from the prototype.** The `select_behaviors = behaviors_for` alias is removed; there is exactly one name.

---

## 5. The Rate-Limiter

A pure, state-threaded throttle. No class, no lock, no module-global state. The caller owns the state dict and threads it forward; concurrency control (if any) is the caller's boundary concern.

```
DedupKey         = { exception_type, file, line }
RateLimitConfig  = { dedup_window_seconds, max_per_hour }
RateLimitDecision = { should_send: Bool, reason: String }   # reason in SUPPRESS_REASONS or ""

dedup_key(report) -> DedupKey
new_state() -> State                                         # { dedup_cache: {}, hourly_sends: [] }
check_rate_limit(key, config, state, now) -> (RateLimitDecision, State')
```

`check_rate_limit` is a pure fold over the prior state:

1. Prune `hourly_sends` older than one hour (relative to `now`).
2. If the hourly count is at `max_per_hour`, return `should_send=False, reason=rate_limit_hourly`.
3. If this key fired within `dedup_window_seconds`, return `should_send=False, reason=rate_limit_dedup`.
4. Otherwise record the send, prune stale dedup entries, return `should_send=True, reason=""`.

It returns a new state; it never mutates its argument. Suppression is **returned data** (`RateLimitDecision`), never an exception or a silent drop — the property that lets honest-test enumerate every suppression path.

**`now` is an argument**, not a clock read. The prototype already does this correctly; the spec makes it normative so the throttle is testable without mocking time (honest-test drives `now` directly).

---

## 6. The Email-Body Formatter

```
format_email_body(report: ExceptionReport) -> String
```

A pure rendering of a report to plain text (severity, environment, time, type, message, location, truncated context, traceback). It performs no sending; an `email` behavior in honest-alerts uses it to build a `Message` body. It is here, not in alerts, because the rendering is a pure function of the `ExceptionReport` shape that honest-errors owns.

---

## 7. Composition Contracts

honest-errors is pure; the I/O lives in the consumers.

**With honest-observe (capture):**

```
report = classify_py_payload(payload, environment, timestamp)        # honest-errors
observe.emit("he.error.captured", report)                            # honest-observe owns the write
```

The `ExceptionReport` is the payload of an error event. honest-observe owns the envelope, the sequence number, and the log; honest-errors owns the report shape.

**With honest-alerts (delivery):**

```
for behavior in behaviors_for(environment):                          # honest-errors
    if behavior.name == "email":
        decision, state = check_rate_limit(dedup_key(report), config, state, now)   # honest-errors
        if decision.should_send or should_bypass_dedup(report.severity):
            alerts.supervisor.deliver(Message(body=format_email_body(report), ...))  # honest-alerts owns the send
```

honest-alerts' supervisor (honest-alerts §1.1) is the general delivery mechanism; honest-errors supplies the *decision* (which behaviors, send-or-suppress) and the *body*, never the transport.

---

## 8. Conformance Requirements

A spoke's honest-errors is conformant iff:

1. **One report shape.** Both normalizers produce the `ExceptionReport` of §2 with identical field decomposition.
2. **Faults as data.** `classify_js_payload` / `classify_py_payload` **return** a `Result`; a malformed payload yields `{ "err": Fault }`, never a raised exception.
3. **No hidden I/O.** No policy function reads the environment, the clock, or any external source; `environment`, `timestamp`, and `now` are arguments.
4. **Bounded vocabularies.** `SEVERITIES`, `ENVIRONMENTS`, `BEHAVIOR_NAMES`, `SUPPRESS_REASONS` match this spec exactly and are frozensets.
5. **Dispatch, not ladders.** `behaviors_for` is a dict lookup with a declared default; severity derivation is a predicate, not an `if/elif` discriminant chain.
6. **Pure throttle.** `check_rate_limit` returns `(decision, new_state)`, never mutates its state argument, takes `now` as an argument, and reports suppression as data.
7. **No delivery, no recording.** The module never logs and never sends; those are honest-observe and honest-alerts respectively.

The cross-tier test-of-record lives in `specs/honest-conformance-suite.md`.

---

## 9. Relationship to the prototype

The Python reference at `python/honest-errors/` predates this spec (distilled from a production exception handler) and already embodies the good ideas it ratifies: two-payload normalization to one report, environment-keyed behavior dispatch as a table, and a pure state-threaded rate-limiter with an injected clock and faults-as-data decisions. The spec is normative; where the prototype diverges, the prototype is the bug:

- The translators read `os.getenv("ENV")` and the system clock internally; §3 requires `environment` and `timestamp` as arguments.
- The translators raise nothing but also cannot signal a malformed payload; §3 requires a `Result` return.
- The closed sets (severity, environment, behavior name, reason) are free `str`; §2.1 requires frozensets.
- The `select_behaviors = behaviors_for` alias is removed (§4).
- The bespoke `RateLimitDecision` reason is bounded to `SUPPRESS_REASONS` (§5).

These are the corrections the spec-first rebuild applies. Everything else in the prototype stands.
