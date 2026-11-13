# honest-errors: Architecture Specification

**Version:** 0.1 (Draft) **Date:** June 2026 **Status:** Active **Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-errors is the Honest Framework's error-policy module. It normalizes a raw failure payload (a browser's JavaScript error object, or a server's Python exception) into one canonical `ExceptionReport`, decides what should *happen* to a report as a function of the environment, and throttles repeat notifications. It does not record the report and it does not send a notification: honest-observe records the report as an event, and honest-alerts delivers any notification the policy calls for.

honest-errors owns the shape of a failure report and the policy that decides what happens to one: the normalization, the environment-to-behavior decision, and the throttle. It also owns the boundary a failure arrives through. A browser error hook or a server error handler catches a failure and calls honest-errors' `capture` door with the raw payload; `capture` runs the whole policy and returns one `FailurePolicy` record carrying the normalized report, the behaviors for the environment, the throttle decision, the next throttle state, and the rendered email body. honest-observe records the report from that result and honest-alerts delivers from it; both read the same `ExceptionReport` type.

### 1.1 The abstract requirement

> *A failure becomes one canonical report; what happens to that report is a pure function of the environment and the report's own content; and repeat notifications are suppressed by a deterministic throttle.*

honest-errors turns the question "what do we do when something breaks?" into data: a normalized report, a list of named behaviors, and a throttle decision. The acts of logging and sending are left to the modules that own those boundaries.

### 1.2 Which bug categories this eliminates (poka-yoke)

| Decision | Bug category made impossible |
|---|---|
| One `ExceptionReport`, two normalizers | Divergent error shapes between the JS and server paths; downstream code branching on source |
| Environment → behaviors as a dispatch table | `if env == "production"` ladders drifting out of sync; an environment silently getting no policy |
| Throttle decision is data (`RateLimitDecision`), never an exception | Notification storms, or a throttle that swallows errors as a side effect instead of reporting suppression |
| Finite vocabularies (severity, environment, behavior, reason) as frozensets | Free-string states that cannot be listed, and so cannot be tested in full or checked ahead of time |
| Environment, time, and `now` are arguments to the policy functions | Hidden environment reads, clock reads, or sends buried inside "pure" policy functions, which is what makes error handling untestable |

### 1.3 Relationship to honest-observe and honest-alerts

honest-errors owns the capture boundary and the policy composition. honest-observe and honest-alerts consume the one `FailurePolicy` that the `capture` door returns. honest-errors depends on neither.

| Consumer | What it takes from a `FailurePolicy` |
|---|---|
| **honest-observe** | The `report`. honest-observe records the normalized `ExceptionReport` as an error event, owning the event envelope, the sequence number, and the log. honest-errors owns the shape of the report; honest-observe owns the write. |
| **honest-alerts** | The `behaviors`, the `decision`, and the `email_body`. When the policy warrants an email (the rendered `email_body` is non-empty, which honest-errors fills only when an `email` behavior applies and the throttle says send or a critical severity bypasses it), honest-alerts' supervisor delivers a `Message` built from the `email_body`. honest-errors owns the decision and the body; honest-alerts owns the transport. |

### 1.4 What honest-errors covers

- The payload IR: `JSErrorPayload`, `PythonExceptionPayload`, and the canonical `ExceptionReport` (all TypedDicts).
- The bounded vocabularies: severities, environments, behavior names, suppression reasons.
- Normalization: `classify_js_payload`, `classify_py_payload` → `Result[ExceptionReport]`.
- Behavior policy: the environment → behaviors dispatch table and `behaviors_for`.
- The rate-limiter: `dedup_key`, `new_state`, `check_rate_limit` (pure, state-threaded, injected clock).
- The email-body formatter (a pure report → text rendering, for use by an `email` behavior).
- The capture boundary and the policy composition: the `capture` door the world enters through, the `handle_failure` orchestrator that runs normalize → behaviors → throttle → render, and the combined `FailurePolicy` it returns.

### 1.5 What honest-errors does not cover

- **Recording the report.** honest-observe writes it to the event log. honest-errors never logs.
- **Sending a notification.** honest-alerts' supervisor delivers it over a channel. honest-errors never sends.
- **Reading the environment or the clock.** The environment, the timestamp, and `now` are passed in as arguments. honest-errors never calls `os.getenv` or reads a wall clock inside a policy function.
- **Deciding raise-versus-log for a fault.** When a normalizer or the policy returns a `Fault`, `capture` returns that `Fault` to its caller; it never raises and never logs. Whether the host re-raises the fault at its own boundary or records it is the host's decision, not honest-errors'.
- **Installing the catch.** honest-errors owns the `capture` door, not the host hook that calls it. A browser's `window.onerror`, an HTTP framework's error handler, or `@catch_at_boundary` is the host's; it catches the raw failure and calls `capture`. honest-errors receives the payload at the door and normalizes it; it never registers itself with the browser or the server.

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
BEHAVIOR_NAMES   = { log, email }                              # frozenset
SUPPRESS_REASONS = { rate_limit_hourly, rate_limit_dedup }     # frozenset
```

**Normative change from the prototype.** These are closed sets and must be declared as frozensets, not free `str` (the prototype documents them in comments but enforces `str`). honest-test enumerates them; honest-check treats them as discriminant sets.

---

## 3. Normalization

```
classify_js_payload(payload, environment, timestamp) -> ExceptionReport | Fault
classify_py_payload(payload, environment, timestamp) -> ExceptionReport | Fault
```

A normalizer returns the `ExceptionReport` on success or a `Fault` on failure, as a union carried by the return value, the framework's fault-by-return convention (honest-type returns `X | Fault` the same way). There is no `{ "ok" } | { "err" }` wrapper: the success type stays visible in the signature.

**Normative change from the prototype.** `environment` and `timestamp` are **arguments**, not read inside the function from `os.getenv` / the system clock. The prototype's translators smuggle both in as hidden I/O; that is the single I/O-at-boundary violation the spec corrects. The boundary that catches the failure already knows the environment and the time; it passes them in.

Each function validates the raw payload against the required keys for its shape and returns a `Fault(code="malformed_payload", ...)` when a required key is absent, otherwise the `ExceptionReport`. Severity for the Python path defaults to `error`. For the JS path a small predicate derives it from the payload: a message is marked `critical` when its text contains the token `critical`, matched case-insensitively, and such a message yields `critical` while every other message yields `error`. It is a predicate, not an `if` ladder that would grow a branch per rule.

### 3.1 `should_bypass_dedup`

```
should_bypass_dedup(severity) -> Bool      # True iff severity == critical
```

A pure predicate. Critical failures are never silenced by the throttle (§5). This is the one product rule honest-errors carries, expressed as data, not control flow.

---

## 4. Behavior Policy

What should happen to a report is a list of named behaviors, looked up by environment.

```
HandlerBehavior = { name: String, order: Integer }   # name in BEHAVIOR_NAMES

BEHAVIORS_BY_ENV = {
    development: [ {log, 0} ],
    production:  [ {log, 0}, {email, 1} ],
    test:        [ {log, 0} ],
}

behaviors_for(environment) -> list[HandlerBehavior] | Fault
```

`behaviors_for` is a pure dict lookup. Adding an environment or changing a policy is editing the table, never editing control flow. An environment the table does not carry has no policy, so `behaviors_for` returns `Fault(code="unknown_environment", ...)`, whose message names the environment it was given and the environments it accepts. It does not fall back to another environment's policy: a fallback files an environment nobody wrote a rule for under a rule written for a different one. The list is *data*: the composing orchestrator interprets each behavior, handing `log` to the output boundary that writes honest-observe's log and `email` to honest-alerts. honest-errors does not execute behaviors; it declares them.

Whether a failure is raised is not a behavior and not a function of the environment. The orchestrator decides whether to raise or log, and only a boundary that declares `raises` may throw.

**Normative change from the prototype.** The `select_behaviors = behaviors_for` alias is removed; there is exactly one name. The `reraise` behavior and the development default are removed as well (§9).

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

`check_rate_limit` is a pure function of the prior state:

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

A failure enters through honest-errors' `capture` boundary and leaves as one `FailurePolicy`. The host catches the failure and calls the door; honest-errors runs the whole policy and returns the result; the consumers read it. The normalize-decide-throttle composition is honest-errors' own, in its `handle_failure` orchestrator, not scattered across the consumers.

**The door and its result:**

```
policy = capture(source, payload, environment, timestamp, config, state, now)   # honest-errors
# policy: FailurePolicy { report, behaviors, decision, next_state, email_body }
```

`capture` is called by the host's error hook — a browser's `window.onerror`, or a server's error boundary such as `@catch_at_boundary`. It forwards the raw payload to `handle_failure`, which normalizes the payload for its `source`, reads `behaviors_for(environment)`, throttles with `check_rate_limit(dedup_key(report), config, state, now)`, and renders `format_email_body(report)` only when an email is warranted: the environment's policy includes an `email` behavior **and** either the throttle says send or a critical severity bypasses the throttle (`should_bypass_dedup`). An environment with no `email` behavior never carries an email body, however the throttle decides. It returns one `FailurePolicy`. A malformed payload, an unknown environment, or a `source` that matches no normalizer comes back as a `Fault` instead (codes `malformed_payload`, `unknown_environment`, `unknown_source`), never a raised exception.

**With honest-observe (recording):**

```
observe.emit("he.error.captured", policy.report)      # honest-observe owns the write
```

The `ExceptionReport` is the payload of an error event. honest-observe owns the envelope, the sequence number, and the log; honest-errors owns the report shape.

**With honest-alerts (delivery):**

```
if policy.email_body:                                  # non-empty only when the policy has an email behavior and the send is warranted
    alerts.supervisor.deliver(Message(body=policy.email_body, ...))   # honest-alerts owns the send
```

honest-alerts' supervisor (honest-alerts §1.1) is the general delivery mechanism; honest-errors supplies the decision (which behaviors, send-or-suppress) and the body, never the transport. The throttle state threads forward through `policy.next_state`: the host passes it as `state` on the next `capture` call.

---

## 8. Conformance Requirements

A spoke's honest-errors is conformant iff:

1. **One report shape.** Both normalizers produce the `ExceptionReport` of §2 with identical field decomposition.
2. **Faults as data, by union.** Every function that can fail returns its success value or a `Fault` as a bare union, never a raised exception and never an `{ "ok" } | { "err" }` wrapper; a `Fault` is a record carrying a `code` and a `message`. `classify_js_payload` / `classify_py_payload` return the `ExceptionReport` or a `malformed_payload` fault; `behaviors_for` returns its list or an `unknown_environment` fault; `handle_failure` / `capture` return a `FailurePolicy` or one of those faults, or an `unknown_source` fault when `source` matches no normalizer.
3. **No hidden I/O.** No policy function reads the environment, the clock, or any external source; `environment`, `timestamp`, and `now` are arguments.
4. **Bounded vocabularies.** `SEVERITIES`, `ENVIRONMENTS`, `BEHAVIOR_NAMES`, `SUPPRESS_REASONS` match this spec exactly and are frozensets.
5. **Dispatch, not ladders.** `behaviors_for` is a dict lookup that returns an `unknown_environment` fault for an environment the table does not carry, never a default; severity derivation is a predicate, not an `if/elif` discriminant chain.
6. **Pure throttle.** `check_rate_limit` returns a `RateLimitOutcome` record `{ decision, next_state }`, never mutates its state argument, takes `now` as an argument, and reports suppression as data (`reason` is `None` on send, a `SUPPRESS_REASONS` word on suppress).
7. **No delivery, no recording.** The module never logs and never sends; those are honest-observe and honest-alerts respectively.
8. **Capture at a boundary, one combined result.** A failure enters through a `capture` boundary, the normalize-decide-throttle composition lives in honest-errors' orchestrator, and the orchestrator returns one `FailurePolicy` (report, behaviors, decision, next state, email body). The consumers read that result; they do not re-implement the composition.
9. **Email body only when an email is warranted.** `FailurePolicy.email_body` is non-empty if and only if the environment's policy includes an `email` behavior **and** either the throttle says send or a critical severity bypasses it. An environment whose policy is log-only never carries an email body, whatever the throttle decides.

The cross-tier test-of-record lives in `specs/honest-conformance-suite.md`.

---

## 9. Relationship to the prototype

The Python reference at `python/honest-errors/` predates this spec (distilled from a production exception handler) and already embodies the good ideas it ratifies: two-payload normalization to one report, environment-keyed behavior dispatch as a table, and a pure state-threaded rate-limiter with an injected clock and faults-as-data decisions. The spec is normative; where the prototype diverges, the prototype is the bug:

- The translators read `os.getenv("ENV")` and the system clock internally; §3 requires `environment` and `timestamp` as arguments.
- The translators raise nothing but also cannot signal a malformed payload; §3 requires a `Result` return.
- The closed sets (severity, environment, behavior name, reason) are free `str`; §2.1 requires frozensets.
- The `select_behaviors = behaviors_for` alias is removed (§4).
- The prototype's development policy carries a `reraise` behavior, and an unknown environment falls back to that policy; §4 removes `reraise` and returns an `unknown_environment` fault instead.
- The bespoke `RateLimitDecision` reason is bounded to `SUPPRESS_REASONS` (§5).

These are the corrections the spec-first rebuild applies. Everything else in the prototype stands.
