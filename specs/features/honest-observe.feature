Feature: honest-observe - generated, one scenario per function (24 total)
  The function-point measure for honest-observe: exactly one scenario per declared
  function, the scenario subject being the function name. 24 functions, 24 scenarios.

  Scenario: new_event_id
    Given no parameters
    When new_event_id is called
    Then it reads the random source and nothing else
    And it returns a fresh UUID v7 event id as a str, time-ordered so the log sorts by creation without a separate column
    But it never reuses an id
    And it raises no fault, being a reader of the world rather than a pure function

  Scenario: event_timestamp
    Given no parameters
    When event_timestamp is called
    Then it reads the clock and nothing else
    And it returns the current wall-clock time as an ISO-8601 microsecond UTC str, the event's timestamp
    But it raises no fault, being a reader of the world rather than a pure function

  Scenario: next_sequence
    Given aggregate_id: str and conn: any
    When next_sequence is called
    Then it reads the event log through the injected database connection conn for the next per-aggregate sequence number
    And it returns an int counter that is unique and increasing within one aggregate_id, fixing order within the aggregate without a global lock
    And it is awaited because the read is I/O
    But conn is never read by any pure function, only held and passed to the boundary

  Scenario: append_event
    Given event: Event and conn: any
    When append_event is called
    Then it appends the one built envelope to the append-only event log through the injected connection conn and returns a WriteOutcome
    And on a clean write the WriteOutcome is ok true with empty detail, and on a failed write it is ok false carrying the error detail
    And it does only the write and builds no Fault, because a boundary is a terminus and leaves fault construction to the orchestrator
    And it is awaited because the append is I/O, and it never raises
    And it issues no update or delete, the log being append-only

  Scenario: run_emit
    Given event_type: str and aggregate_type: str and aggregate_id: str and payload: dict and context: dict and event_version: str and conn: any
    When run_emit is called
    Then it is the single mutator of the event value, invoking its own readers new_event_id, event_timestamp and next_sequence to pull the three impure parts
    And it invokes extract_auth and extract_meta to pull the auth and meta partitions from context
    And it hands all parts to build_event, which assembles and validates one immutable envelope, and applies each return into the one value without any pure function mutating
    And on a build_event Fault (an empty required field) it returns the Fault without writing
    And otherwise it appends through append_event, reads the WriteOutcome, and returns the event on a clean write or builds the emit_failed Fault via observe_fault on a failed one
    And it is awaited because next_sequence and append_event are I/O
    But it returns Event | Fault so the fault bubbles to the door by return, never a swallowed log line

  Scenario: emit
    Given event_type: str and aggregate_type: str and aggregate_id: str and payload: dict and context: dict and event_version: str and conn: any
    When emit is called
    Then it is the one door that writes an event to the log, called from inside an application chain link declared at the boundary
    And it hands its input to run_emit and returns what run_emit returns, the appended Event or a Fault
    And it is awaited because run_emit is
    But it returns Event | Fault rather than raising, because the calling link decides whether a failed emit stops its chain
    And nothing inside the module calls it, the world calling in here

  Scenario: extract_auth
    Given context: dict
    When extract_auth is called
    Then it pulls the auth partition out of the current manifest at the context's auth key for attachment to the envelope
    And it returns that block as a dict, carried verbatim and copied without inspecting a field
    But it is pure, a map read with no world and no fault

  Scenario: extract_meta
    Given context: dict
    When extract_meta is called
    Then it pulls the optional application-metadata partition out of the current manifest at the context's meta key
    And it returns that open map as a dict, carried verbatim and never read by the framework
    But it is pure, a map read with no world and no fault

  Scenario: build_event
    Given event_type: str and event_version: str and aggregate_type: str and aggregate_id: str and payload: dict and auth: dict and meta: dict and event_id: str and timestamp: str and sequence: int
    When build_event is called
    Then it assembles one immutable Event envelope from its already-computed parts and validates it, being the one place the envelope is built
    And it returns the Event
    But when a required field is empty it returns a Fault with code empty_required_field as a bare union arm (Event | Fault), never raising
    And it is a pure constructor, the impure parts event_id, timestamp and sequence and the extracted auth and meta passed in, so it runs without a clock, a random source or a database

  Scenario: observe_fault
    Given code: str and message: str and detail: dict
    When observe_fault is called
    Then it builds one observe Fault record from its parts, the single place honest-observe assembles a fault
    And it sets the reserved is_err tag true and returns the Fault, recognized by is_fault, never raised and never wrapped in an ok/err envelope
    And build_event invokes it for an empty required field and run_emit invokes it for a failed append
    But it is pure, reading no world

  Scenario: request_canonical
    Given request_id: str and http_method: str and http_path: str and http_status: int and caller_id: str and session_id: str and chain_name: str and link_count: int and link_sequence: list and token_count: int and rejection_count: int and query_count: int and query_duration_ns: int and result: str and fault_code: str and fault_category: str and duration_ns: int
    When request_canonical is called
    Then it assembles the one dense canonical request Event emitted last for every request, colocating all request telemetry in one record so an operational question needs no join
    And it folds the facts already gathered for the request into one Event keyed by request_id, the join key with the browser events
    But it is pure, folding facts in hand, reading no world and returning no fault

  Scenario: matches
    Given event: Event and event_types: list
    When matches is called
    Then it returns true when the event's type is one of the requested event_types, being the one place the event-type filter is decided
    And it returns a bool
    But it is pure, a membership test with no world and no fault

  Scenario: apply_projection
    Given projection: Projection and events: list and fold: Callable and initial_state: any
    When apply_projection is called
    Then it reads the projection handle's event_types and invokes matches to keep only the events the projection filters to, then folds them in order into a derived read model
    And the filter lives in the one Projection handle and is not copied into a loose argument beside it
    And fold is the pure (state, event) -> state accumulator and initial_state its seed, returning new state each step
    And it returns the folded state as any, the only read path over the raw log, reached by import
    But it is pure, no I/O and no mutation, so a projection cannot drift from the log

  Scenario: declare_projection
    Given projection_id: str and event_types: list and fold: Callable and initial_state: any
    When declare_projection is called
    Then it declares a named projection, returning the flat Projection handle registered under projection_id over the given event_types
    And fold and initial_state are named here and passed to apply_projection at run time, so they are not stored in the serializable handle
    But it is pure, building a record, reading no world and returning no fault, reached by import

  Scenario: build_snapshot
    Given projection_id: str and snapshot_at: str and state: any
    When build_snapshot is called
    Then it builds a projection snapshot, packaging projection_id, the log position snapshot_at it covers, and the folded state at that position into a snapshot record
    And it returns that snapshot as any, so a projection over millions of events need not replay from the beginning every time
    But it is pure, reading no world and returning no fault, reached by import

  Scenario: resume_from_snapshot
    Given projection: Projection and snapshot: any and events: list and fold: Callable
    When resume_from_snapshot is called
    Then it reads the projection handle's event_types and invokes matches to keep only the filtered events in the log tail, folding them onto the snapshot's prior state with the same pure accumulator fold
    And it returns the resumed state as any, equal to a full replay, so a snapshot cannot change the answer
    But it is pure, no I/O and no mutation, reached by import

  Scenario: otel_signal
    Given event: Event
    When otel_signal is called
    Then it projects one event to its OpenTelemetry signal (a trace span, child span, span event or metric) as pure data carrying the standard and hf.* semantic-convention attributes
    And the signal kind follows the event type as a mapping read from the event, not a branch ladder
    And it returns the signal value as any, reached by import
    But it emits no signal itself, shipping being boundary I/O through an injected exporter, so observe never imports the OTel SDK
    And it is pure, an Event in and a signal value out, no world and no fault

  Scenario: compute_metric
    Given metric: Metric and events: list
    When compute_metric is called
    Then it computes the metric's value by folding its source events, the metric's own fold, value and group functions passed in with it
    And for a plain metric it returns one number and for a grouped metric it returns a mapping of group key to value, so a per-group threshold can test each group
    And it returns the value as any, reached by import and invoked by evaluate_threshold
    But it is pure, events in and value out, no world and no fault

  Scenario: threshold_projection
    Given projection_id: str and metric: str and condition: any and window: str and cooldown: str and alert: any and enabled: bool
    When threshold_projection is called
    Then it declares a threshold projection that watches the named metric and fires alert when condition is crossed over window, with cooldown the minimum time between firings and enabled the operator toggle
    And it returns a ThresholdProjection record carrying projection_id, metric, condition, window, cooldown, alert and enabled
    And the return is a ThresholdProjection, not a Projection, whose two fields cannot carry a firing decision's terms
    But it is pure, building a record, reading no world and returning no fault, reached by import

  Scenario: evaluate_threshold
    Given threshold: ThresholdProjection and metric: Metric and events: list
    When evaluate_threshold is called
    Then it reads the ThresholdProjection's condition, invokes compute_metric on the Metric handle to get the value, and tests the condition
    And for a plain metric the decision is whether the one value crossed, and for a grouped metric it returns { fired, firings } where fired is true when any group crossed and firings carries one { group, fired, value } record per group
    And it returns the decision as any, the send to honest-alerts being a separate boundary the caller runs, reached by import
    But it is pure, events in and decision out, no world and no fault

  Scenario: hlc_send
    Given local: dict and physical_now: int
    When hlc_send is called
    Then it advances a hybrid logical clock for a send, giving a total order across sources that respects causality without a synchronized wall clock
    And it sets physical to the max of physical_now and local's physical, and increments the logical counter when physical did not advance so same-millisecond events still order
    And it returns the new HLC as a dict
    But it is pure, two values in and the new HLC out, no world (physical_now is passed, not read) and no fault

  Scenario: hlc_receive
    Given local: dict and incoming: dict and physical_now: int
    When hlc_receive is called
    Then it advances a hybrid logical clock on receiving an event from another source, so one source keeps its order and events across sources interleave by physical time
    And it advances physical to the max of the three physicals and sets the logical counter so causality is preserved, breaking ties by source id
    And it returns the new HLC as a dict
    But it is pure, three values in and the new HLC out, no world and no fault

  Scenario: fold_identity_claims
    Given events: list
    When fold_identity_claims is called
    Then it folds the identity.claimed events into the identity binding table, a projection mapping (external_system, external_id) to a canonical id
    And it reduces each append-only claim into a lookup and returns the bindings as a dict
    And a conflict, two claims mapping one external id to different canonical ids, is surfaced in the result for human adjudication, not silently resolved
    But it is pure, events in and bindings out, no world and no fault, reading the log slice it is handed, reached by import

  Scenario: resolve_identity
    Given external_id: str and source: str and bindings: dict
    When resolve_identity is called
    Then it resolves one external_id in a source to its canonical id by looking it up in the bindings table that fold_identity_claims produced, returning the canonical id as a str
    But an unresolvable id is a bounded absence, not a failure: it returns NOTHING, which carries no is_err tag and is never recognized by is_fault, keeping it disjoint from a Fault
    And it is pure, a table lookup with no world, reached by import

  Scenario: event_log_schema
    Given no parameters
    When event_log_schema is called
    Then it returns the honest_event_log table manifest as data, the append-only event-log schema honest-persist enforces, with update and delete rejected against the table
    And it names the columns of the envelope and the indexes the common projection filters need: by event type, by aggregate, by timestamp, and by aggregate-and-sequence
    But it is pure, taking no argument because the schema is fixed, reading no world and returning no fault, reached by import so honest-persist's migration can create the table from one declared shape
