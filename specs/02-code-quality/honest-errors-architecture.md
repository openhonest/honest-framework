# honest-errors: Architecture Specification

**Version:** 0.2 **Status:** Active **Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-errors is the Honest Framework's error-cadence module. It normalizes a raw failure payload (a browser's JavaScript error object, or a server's Python exception) into one canonical `ExceptionReport`, and it carries out the cadence the caller declares for that failure: whether the failure needs a response, whether the response goes back to the caller or is a bare acknowledgement, whether the failure is displayed once or for a period, and whether it displays now or on a schedule. It does not record the report and it does not send a notification: honest-observe records the report as an event, and honest-alerts delivers any notification the cadence calls for.

honest-errors owns three things: the shape of a failure report, the cadence declaration the caller writes, and the cadence state that declaration becomes once it is inside the module. A host error hook catches a failure and calls honest-errors' `capture` door with the raw payload and a cadence declaration; `capture` normalizes the payload, enacts the cadence against the module's own state, and returns one `CaptureResult` carrying the normalized report, the response for the caller, and the display actions due now. honest-observe records the report from that result and honest-alerts delivers from it.

### 1.1 The abstract requirement

> *A failure becomes one canonical report. The caller declares, as data, how that failure is handled. honest-errors holds the resulting cadence as its own state, mutated in one place and persisted so a held or scheduled display survives a restart.*

honest-errors turns the question "what do we do when something breaks?" into two data artifacts: a normalized report, and a cadence the caller declares and the module keeps. The acts of recording and sending are left to the modules that own those boundaries.

### 1.2 The declarative surface

The caller does not call step functions and does not thread the module's state back in. It hands honest-errors a failure and a declaration of what to do with it, written as data. The declaration is a **chain of typed action parameters**: each action the module offers is its own named, typed parameter, present with a typed value or explicitly absent. A reader sees every action honest-errors offers by reading the `Cadence` type, because the set of actions is closed and finite. This is the difference from a list of actions, which is open and untyped and tells a reader nothing about which actions exist.

The declaration answers four questions about the failure:

1. Does this failure need a response, or is normalizing and recording it enough?
2. If it needs a response, does the response go back to the caller, or does the module return a bare acknowledgement?
3. Is the failure displayed once, or held for a set period?
4. Does it display immediately, or on a schedule?

Questions 1 and 2 are the **response**. Questions 3 and 4 are the **display**: its duration and its timing.

### 1.3 Which bug categories this eliminates (poka-yoke)

| Decision | Bug category made impossible |
|---|---|
| One `ExceptionReport`, two normalizers | Divergent error shapes between the JS and server paths; downstream code branching on source |
| The caller declares the cadence as typed action parameters | A handling policy that drifts inside the module out of the caller's sight; an environment silently getting no policy |
| Each action parameter carries an explicit `Absent` | An omitted action read as a forgotten one; an untested input region manufactured by an implicit default |
| The cadence is state honest-errors owns, with one declared mutator | A second writer of the same display state; a display that two code paths both change and neither owns |
| The cadence state persists | A held or scheduled display lost on restart, so an error silently stops displaying or never fires |
| Finite vocabularies (severity, environment, response mode) as closed sets, duration and timing as bounded unions | Free-string states that cannot be listed, and so cannot be tested in full or checked ahead of time |
| Environment, time, and `now` are arguments | Hidden environment reads, clock reads, or sends buried inside a policy function, which is what makes error handling untestable |

### 1.4 Relationship to honest-observe and honest-alerts

honest-errors owns the capture boundary, the cadence declaration, and the cadence state. honest-observe and honest-alerts consume the one `CaptureResult` that `capture` returns. honest-errors depends on neither.

| Consumer | What it takes from a `CaptureResult` |
|---|---|
| **honest-observe** | The `report`. honest-observe records the normalized `ExceptionReport` as an error event, owning the event envelope, the sequence number, and the log. honest-errors owns the shape of the report; honest-observe owns the write. |
| **honest-alerts** | The `actions`. Each is a display or send that the cadence makes due now (an immediate display, or a scheduled one whose time has arrived). honest-alerts delivers each over its channel. honest-errors owns the decision of what is due; honest-alerts owns the transport. |

### 1.5 What honest-errors does not cover

- **Recording the report.** honest-observe writes it to the event log. honest-errors never logs.
- **Sending a notification.** honest-alerts' supervisor delivers it over a channel. honest-errors never sends.
- **Reading the environment or the clock.** The environment, the timestamp, and `now` are passed in as arguments. honest-errors never calls `os.getenv` or reads a wall clock inside a policy function.
- **Installing the catch.** honest-errors owns the `capture` door, not the host hook that calls it. A browser's `window.onerror`, an HTTP framework's error handler, or `@catch_at_boundary` is the host's; it catches the raw failure and calls `capture`.

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

The two payload shapes collapse to one report so that every downstream consumer — the observe event, the alerts notification — is source-agnostic.

### 2.1 Bounded vocabularies

```
SEVERITIES     = { debug, info, warning, error, critical }   # closed set
ENVIRONMENTS   = { development, production, test }            # closed set
RESPONSE_MODES = { returned, acknowledged }                  # closed set
```

These are closed sets, declared as frozensets, never free `str`. honest-test enumerates them; honest-check treats them as discriminant sets.

---

## 3. Normalization

```
classify_js_payload(payload, environment, timestamp) -> ExceptionReport | Fault
classify_py_payload(payload, environment, timestamp) -> ExceptionReport | Fault
```

A normalizer returns the `ExceptionReport` on success or a `Fault` on failure, as a union carried by the return value — the framework's fault-by-return convention. The `Fault` is the error branch of the function's decision table, returned as an ordinary value and recognized by its own shape, never raised and never wrapped in an envelope. The success type stays visible in the signature. A `Fault` is a record carrying at least a `code` and a `message`.

`environment` and `timestamp` are **arguments**, not read inside the function from `os.getenv` or the system clock. The boundary that catches the failure already knows the environment and the time; it passes them in.

Each function validates the raw payload against the required keys for its shape and returns a `Fault(code="malformed_payload", ...)` when a required key is absent, otherwise the `ExceptionReport`. Severity for the Python path is `error`. For the JS path a small predicate derives it from the payload: a message whose text contains the token `critical`, matched case-insensitively, yields `critical`; every other message yields `error`. It is a predicate, not an `if` ladder that would grow a branch per rule.

---

## 4. The Cadence Declaration

The caller's declaration is the `Cadence`, a chain of typed action parameters. Each parameter is present with a typed value or explicitly `Absent`.

```
ResponseSpec = { mode: ResponseMode }           # ResponseMode in RESPONSE_MODES
Duration     = Once | Period                     # bounded union
Period       = { seconds: Integer }
Timing       = Immediate | Scheduled             # bounded union
Scheduled    = { at: String }                    # ISO-8601
DisplaySpec  = { duration: Duration, timing: Timing }

Cadence = {
    respond: ResponseSpec | Absent,              # Q1 present/absent, Q2 the mode
    display: DisplaySpec | Absent,               # Q3 the duration, Q4 the timing
}
```

- **`respond`** answers the first two questions. `Absent` means the failure needs no response: normalizing and recording it is enough. Present means it needs one, and `mode` says whether the caller gets the normalized report back (`returned`) or a bare acknowledgement that the failure was captured (`acknowledged`).
- **`display`** answers the last two questions. `Absent` means the failure is not displayed. Present means it is, `duration` says whether it shows once or for a `Period` of seconds, and `timing` says whether it displays `Immediate`-ly or `Scheduled` for a later time.

Each parameter carries an explicit `Absent` rather than a default, so "the caller did not ask for a display" is a bounded case a test exercises, not a silent omission.

### 4.1 Presets and the naming sugar

A caller that wants a common handling does not write the full `Cadence`. honest-errors offers named presets, and the caller names one.

```
PRESET_NAMES = { silent, acknowledge, report_back, notify }   # closed set

PRESETS = {
    silent:      { respond: Absent,         display: Absent },
    acknowledge: { respond: {acknowledged}, display: Absent },
    report_back: { respond: {returned},     display: Absent },
    notify:      { respond: {acknowledged}, display: {Once, Immediate} },
}

resolve_cadence(arg: Cadence | PresetName) -> Cadence | Fault
```

A preset is a named `Cadence`, and each preset falls into the actions §4 lists. `PRESETS` is a dispatch table from a preset name to its `Cadence`, so adding or changing a preset is editing the table, never control flow, and `PRESET_NAMES` is the closed set of names the sugar accepts. `resolve_cadence` takes what the caller passed: a full `Cadence` passes through unchanged, and a `PresetName` resolves to its `Cadence` by table lookup. A name the table does not carry returns a `Fault(code="unknown_preset", ...)`, whose message names the presets it accepts. The discrimination between a record and a name is a recognizer on the argument, not an `if`. The caller chooses the preset; honest-errors does not pick one from the environment or any other hidden input.

---

## 5. The Cadence State and Its Single Mutator

A display held for a period, or scheduled for later, is state. honest-errors owns it. It is not threaded by the caller and not read from any global; it lives in the module and is persisted so that a held or scheduled display survives a restart.

```
DisplayStatus = Showing | Pending                # bounded union: showing now, or scheduled and not yet due
LiveDisplay   = { key: DedupKey, status: DisplayStatus, until: String | Absent, due: String | Absent }
DedupKey      = { exception_type, file, line }
CadenceState  = { live: list<LiveDisplay> }
```

`DedupKey` is the display identity of a report: two failures with the same type, file, and line are the same display. A `display` declared `Once` adds the key at most one live entry, so the same failure does not re-display while its entry is live.

**The orchestrator is the single mutator of `CadenceState`.** The pure functions compute; they do not mutate. From the current state, the new report, the cadence, and `now`, they return the next state and the actions due now:

```
advance_cadence(state, report, cadence, now) -> (CadenceState', list<DisplayAction>)
```

`advance_cadence` and the pure functions it composes return a new state and never mutate the argument. They expire the entries whose `until` has passed, release the `Pending` entries whose `due` has arrived, and add the new report's entry per the declaration. The orchestrator takes their returned `CadenceState'`, writes it as the module's one owned, persisted state, and returns the `DisplayAction` list for honest-alerts. One function applies the change, so a reader sees the single place the cadence state moves (the single-mutator law, read from the orchestrator's side: `honest-state-architecture.md` §1.2).

```
DisplayAction = { key: DedupKey, report: ExceptionReport, kind: ActionKind }
ActionKind    = show | hide | send              # closed set
```

A `DisplayAction` is a decision, not a delivery: honest-errors says what is due, honest-alerts does it.

---

## 6. The Capture Boundary and Its Result

A failure enters through honest-errors' `capture` boundary and leaves as one `CaptureResult`. The host catches the failure and calls the door; honest-errors runs the whole cadence and returns the result; the consumers read it.

```
capture(source, payload, environment, timestamp, cadence, now) -> CaptureResult | Fault
# CaptureResult { report, response, actions }
```

`capture` forwards the raw payload to the `handle_failure` orchestrator. `handle_failure` resolves the preset (`resolve_cadence`), then composes the steps — normalize the payload for its `source`, build the caller's `response` from the `respond` spec, and `advance_cadence` to move the owned cadence state and collect the `actions` due now — as a chain the honest-type §12 executor runs. The executor recognizes a link's returned `Fault` (the error branch of its decision table) and short-circuits on it, so `handle_failure` writes no guard clause: a malformed payload (`malformed_payload`), a `source` that matches no normalizer (`unknown_source`), or an unknown preset (`unknown_preset`) stops the chain and is returned as the `Fault`. On success the chain returns the `CaptureResult`. honest-errors never raises; the host decides what to do with a returned `Fault`.

```
response: the normalized report when respond.mode is returned,
          a bare acknowledgement when it is acknowledged,
          Absent when respond is Absent.
```

The caller reads `response` synchronously. honest-observe reads `result.report`. honest-alerts reads `result.actions` and delivers each. The cadence state does not appear in the result and is not threaded by the caller: honest-errors owns it and persists it between calls.

---

## 7. Conformance Requirements

A spoke's honest-errors is conformant iff:

1. **One report shape.** Both normalizers produce the `ExceptionReport` of §2 with identical field decomposition.
2. **Faults as data, by return.** Every function that can fail returns its success value or a `Fault` as a union carried by the return value, never a raised exception and never wrapped in an envelope; the `Fault` is the error branch of the function's decision table, recognized by its own shape, and a `Fault` is a record carrying at least a `code` and a `message`. `classify_js_payload` / `classify_py_payload` return `ExceptionReport | Fault` (a `malformed_payload` fault); `resolve_cadence` returns `Cadence | Fault` (an `unknown_preset` fault); `capture` / `handle_failure` return `CaptureResult | Fault` (a `malformed_payload`, `unknown_source`, or `unknown_preset` fault).
3. **No hidden I/O.** No policy function reads the environment, the clock, or any external source; `environment`, `timestamp`, and `now` are arguments.
4. **The caller declares the cadence.** The handling of a failure is the `Cadence` the caller passes, a chain of typed action parameters, each present with a typed value or explicitly `Absent`. honest-errors does not derive it from hidden state.
5. **Bounded vocabularies and bounded unions.** `SEVERITIES`, `ENVIRONMENTS`, `RESPONSE_MODES` are closed frozensets matching this spec; `Duration`, `Timing`, `DisplayStatus`, and `ActionKind` are bounded unions.
6. **One owned, persisted cadence state with one mutator.** `CadenceState` is honest-errors' own state, written by exactly one mutator — the orchestrator, applying the returns of the pure `advance_cadence` composition — and persisted so a held or scheduled display survives a restart. No pure function mutates it, and no caller threads it.
7. **No delivery, no recording.** The module never logs and never sends; those are honest-observe and honest-alerts respectively.
8. **Capture at a boundary, one combined result, composed as a chain.** A failure enters through a `capture` boundary; `handle_failure` composes the normalize-respond-advance steps as a chain the honest-type §12 executor runs, which recognizes a link's returned `Fault` and short-circuits on it with no guard clause; and it returns one `CaptureResult | Fault` (report, response, actions). The consumers read that result; they do not re-implement the composition.

The cross-tier test-of-record lives in `specs/honest-conformance-suite.md`.
