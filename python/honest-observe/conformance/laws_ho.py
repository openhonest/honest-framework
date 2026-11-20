"""honest-observe generative laws: the I/O emit path driven against a REAL in-memory sqlite event
log (never a mock of our own code), plus the structural invariants of the pure functions whose whole
output the one-line feature scenario does not fix (so a whole-dict value_case would assert a shape the
spec never pinned). The portable value_cases in suite.json carry the fully-fixed pure functions
(extract_auth, extract_meta, build_event-ok, matches, apply_projection); these laws carry the rest.

A Fault here is a bare union arm: a dict with is_err True, code, message, detail, recognized by
honest_type.is_fault off the reserved is_err tag. There is no ok/err envelope. emit, run_emit,
append_event and build_event return Event | Fault (honest-observe.hd, Fault note).

The emit readers new_event_id and event_timestamp read random and the clock, so they are
non-deterministic: the laws assert STRUCTURAL invariants (a fresh id is a non-empty str, two reads
differ; a timestamp is a non-empty str), never a fixed value.
"""

import asyncio
import json
import sqlite3

import honest_observe as HO
from honest_type import is_fault


def _conn():
    """A real in-memory sqlite connection: the integration boundary, not a mock. The event-log table
    is created from the module's own declared schema manifest, so the laws never hardcode the coder's
    columns -- event_log_schema() is the single declared shape honest-persist's migration would use."""
    conn = sqlite3.connect(":memory:")
    _create_log(conn)
    return conn


def _create_log(conn):
    """Create the honest_event_log table from event_log_schema()'s manifest. The manifest names the
    table and its columns; the laws read those names rather than assuming them, so the schema stays the
    one declared shape (honest-observe.hd event_log_schema note, section 10)."""
    manifest = HO.event_log_schema()
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
    conn.commit()


def _row_count(conn):
    table = HO.event_log_schema()["table"]
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


_CONTEXT = {"auth": {"caller_id": "u1", "session_id": "s1"}, "meta": {"release": "r1"}}


def _emit_args(event_type="order.placed", aggregate_id="ord-1", payload=None, context=None):
    return (
        event_type,
        "order",
        aggregate_id,
        {"total": 10} if payload is None else payload,
        _CONTEXT if context is None else context,
        "1.0",
    )


# --- the impure readers (structural, non-deterministic) --------------------------------------------


def _law_new_event_id():
    bad = []
    a = HO.new_event_id()
    b = HO.new_event_id()
    if not isinstance(a, str) or not a:
        bad.append(f"new_event_id must return a fresh non-empty str: {a!r}")
    if a == b:
        bad.append("new_event_id must never reuse an id: two reads returned the same value")
    return bad


def _law_event_timestamp():
    bad = []
    ts = HO.event_timestamp()
    if not isinstance(ts, str) or not ts:
        bad.append(f"event_timestamp must return a non-empty ISO-8601 str: {ts!r}")
    return bad


def _law_next_sequence():
    bad = []
    conn = _conn()
    # next_sequence is a pure read: it derives MAX(sequence)+1 from the log, so a fresh aggregate reads
    # 0 and the value reflects what has been appended. Two bare reads with no append between are equal,
    # not increasing; the per-aggregate increase across appends is what matters, and it holds here and in
    # _law_run_emit_sequence_increases. It never writes (a reader does not write), so it is idempotent.
    first = asyncio.run(HO.next_sequence("agg-A", conn))
    if first != 0:
        bad.append(f"next_sequence for a fresh aggregate must read 0 from the empty log: {first!r}")
    again = asyncio.run(HO.next_sequence("agg-A", conn))
    if again != first:
        bad.append(f"next_sequence is a pure read: two reads with no append between must agree: {first} then {again}")
    event = HO.build_event("t", "1.0", "agg", "agg-A", {}, {}, {}, "eid-seq", "2026-01-01T00:00:00.000000Z", first)
    asyncio.run(HO.append_event(event, conn))
    after = asyncio.run(HO.next_sequence("agg-A", conn))
    if after != 1:
        bad.append(f"after one append next_sequence must read 1 (MAX+1 within the aggregate): {after!r}")
    other = asyncio.run(HO.next_sequence("agg-B", conn))
    if other != 0:
        bad.append(f"next_sequence counts independently per aggregate: agg-B must be 0, got {other!r}")
    return bad


# --- the write boundary and the emit path (real log) -----------------------------------------------


def _law_append_event_appends_one():
    bad = []
    conn = _conn()
    event = HO.build_event(
        "order.placed", "1.0", "order", "ord-1", {"total": 10},
        {"caller_id": "u1"}, {"release": "r1"}, "eid-1", "2026-01-01T00:00:00.000000Z", 1,
    )
    if is_fault(event):
        bad.append(f"build_event on complete parts must return an Event, not a Fault: {event}")
        return bad
    before = _row_count(conn)
    out = asyncio.run(HO.append_event(event, conn))
    after = _row_count(conn)
    if after - before != 1:
        bad.append(f"append_event must append exactly one row: {before} -> {after}")
    # append_event does only the write: it reports a WriteOutcome, never the Event and never a Fault.
    if is_fault(out):
        bad.append(f"append_event is a terminus boundary: it reports a WriteOutcome, it does not build a Fault: {out}")
    elif out.get("ok") is not True:
        bad.append(f"a clean write must report WriteOutcome ok true: {out}")
    elif out.get("detail") != "":
        bad.append(f"a clean write's WriteOutcome detail must be empty: {out.get('detail')!r}")
    return bad


def _law_append_event_serializes_maps_as_json():
    bad = []
    conn = _conn()
    table = HO.event_log_schema()["table"]
    # Non-trivial maps for the three map columns (payload, auth, meta), each carrying nested structure
    # so the stored form is unambiguous: json.dumps double-quotes and nests, str() of a dict single-
    # quotes. Reading the stored cells back is what pins the serialization append_event must use.
    payload = {"total": 10, "items": ["a", "b"]}
    auth = {"caller_id": "u1", "roles": ["admin", "ops"]}
    meta = {"release": "r1", "flags": {"beta": True}}
    event = HO.build_event(
        "order.placed", "1.0", "order", "ord-json", payload, auth, meta,
        "eid-json", "2026-01-01T00:00:00.000000Z", 0,
    )
    if is_fault(event):
        bad.append(f"build_event on complete parts must return an Event: {event}")
        return bad
    asyncio.run(HO.append_event(event, conn))
    row = conn.execute(f"SELECT payload, auth, meta FROM {table} WHERE event_id = ?", ("eid-json",)).fetchone()
    if row is None:
        bad.append("append_event must store the event so its map columns can be read back")
        return bad
    for stored, name, value in zip(row, ("payload", "auth", "meta"), (payload, auth, meta)):
        # The map column must land as JSON (json.dumps), not str(): the stored cell equals the json.dumps
        # form exactly, and loads back to the original dict. Under str() the cell is single-quoted and is
        # not valid JSON, so both checks fail and a mutant dropping a column from _JSON_COLUMNS is caught.
        if stored != json.dumps(value):
            bad.append(f"the {name} map column must be stored as JSON (json.dumps), not str(): got {stored!r}")
            continue
        if json.loads(stored) != value:
            bad.append(f"the stored {name} JSON must round-trip to the original map: {stored!r}")
    return bad


def _law_append_event_failure_outcome():
    bad = []
    conn = _conn()
    conn.close()  # a closed real connection makes the write fail at the boundary
    event = HO.build_event(
        "order.placed", "1.0", "order", "ord-1", {"total": 10},
        {"caller_id": "u1"}, {"release": "r1"}, "eid-2", "2026-01-01T00:00:00.000000Z", 1,
    )
    out = asyncio.run(HO.append_event(event, conn))
    # A failed write is a WriteOutcome ok false carrying the error detail, NOT a Fault: the boundary is
    # a terminus and leaves fault construction to run_emit.
    if is_fault(out):
        bad.append(f"append_event must not build a Fault on failure; it reports a WriteOutcome: {out}")
        return bad
    if out.get("ok") is not False:
        bad.append(f"a failed write must report WriteOutcome ok false: {out}")
    if not out.get("detail"):
        bad.append(f"a failed write's WriteOutcome must carry the error detail for run_emit to put in the fault: {out}")
    return bad


def _law_run_emit_append_failure_builds_fault():
    bad = []
    conn = _conn()
    conn.execute("PRAGMA query_only = ON")  # reads (next_sequence) still work; only the append write fails
    out = asyncio.run(HO.run_emit(*_emit_args(), conn))
    # run_emit, the orchestrator, reads the failed WriteOutcome and builds the emit_failed Fault via
    # observe_fault (a forward orchestrator -> pure call), since the boundary may not build it.
    if not is_fault(out):
        bad.append(f"run_emit must return a Fault when the append fails: {out}")
    elif out.get("is_err") is not True:
        bad.append(f"the emit_failed Fault must carry the reserved is_err tag true: {out}")
    elif out.get("code") != "emit_failed":
        bad.append(f"a failed append must make run_emit return code emit_failed: {out.get('code')!r}")
    return bad


def _law_run_emit_appends_and_returns_event():
    bad = []
    conn = _conn()
    before = _row_count(conn)
    out = asyncio.run(HO.run_emit(*_emit_args(), conn))
    after = _row_count(conn)
    if is_fault(out):
        bad.append(f"run_emit on a complete event must return the appended Event: {out}")
        return bad
    if after - before != 1:
        bad.append(f"run_emit must append exactly one complete envelope: {before} -> {after}")
    for field in ("event_id", "event_type", "timestamp", "sequence", "aggregate_id", "payload", "auth", "meta"):
        if field not in out:
            bad.append(f"the appended envelope is missing required field {field}: {out}")
    if out.get("event_type") != "order.placed":
        bad.append(f"run_emit must carry the given event_type: {out.get('event_type')!r}")
    if out.get("auth") != {"caller_id": "u1", "session_id": "s1"}:
        bad.append(f"run_emit must attach the extracted auth partition verbatim: {out.get('auth')}")
    if out.get("meta") != {"release": "r1"}:
        bad.append(f"run_emit must attach the extracted meta partition verbatim: {out.get('meta')}")
    return bad


def _law_run_emit_sequence_increases():
    bad = []
    conn = _conn()
    a = asyncio.run(HO.run_emit(*_emit_args(aggregate_id="ord-9"), conn))
    b = asyncio.run(HO.run_emit(*_emit_args(aggregate_id="ord-9"), conn))
    if is_fault(a) or is_fault(b):
        bad.append(f"two emits into one aggregate must both succeed: {a}, {b}")
        return bad
    if not (isinstance(a.get("sequence"), int) and isinstance(b.get("sequence"), int)):
        bad.append(f"the envelope sequence must be an int: {a.get('sequence')!r}, {b.get('sequence')!r}")
    elif not b["sequence"] > a["sequence"]:
        bad.append(f"sequence must increase within one aggregate_id: {a['sequence']} then {b['sequence']}")
    return bad


def _law_run_emit_empty_required_field_faults_and_writes_nothing():
    bad = []
    conn = _conn()
    before = _row_count(conn)
    out = asyncio.run(HO.run_emit(*_emit_args(event_type=""), conn))
    after = _row_count(conn)
    if not is_fault(out):
        bad.append(f"an empty required field must make run_emit return a Fault: {out}")
    elif out.get("is_err") is not True:
        bad.append(f"the build Fault must carry is_err true: {out}")
    elif out.get("code") != "empty_required_field":
        bad.append(f"an empty required field must carry code empty_required_field: {out.get('code')!r}")
    if after != before:
        bad.append(f"run_emit must write nothing when build_event faults: {before} -> {after}")
    return bad


def _law_emit_delegates_to_run_emit():
    bad = []
    conn = _conn()
    before = _row_count(conn)
    out = asyncio.run(HO.emit(*_emit_args(), conn))
    after = _row_count(conn)
    if is_fault(out):
        bad.append(f"emit on a complete event must return the appended Event: {out}")
        return bad
    if after - before != 1:
        bad.append(f"emit is the one door: it must append exactly one envelope: {before} -> {after}")
    if out.get("event_type") != "order.placed":
        bad.append(f"emit must return the appended Event run_emit produced: {out}")
    return bad


# --- build_event's fault arm (only the code/is_err are fixed by the scenario) ----------------------


def _law_build_event_empty_required_field():
    bad = []
    out = HO.build_event(
        "", "1.0", "order", "ord-1", {"total": 10},
        {"caller_id": "u1"}, {"release": "r1"}, "eid-1", "2026-01-01T00:00:00.000000Z", 1,
    )
    if not is_fault(out):
        bad.append(f"build_event with an empty required field must return a Fault arm: {out}")
        return bad
    if out.get("is_err") is not True:
        bad.append(f"the build Fault must carry the reserved is_err tag true: {out}")
    if out.get("code") != "empty_required_field":
        bad.append(f"the build Fault must carry code empty_required_field: {out.get('code')!r}")
    # The detail names the empty field so emit can say which one, and the message names it too.
    if out.get("detail") != {"fields": ["event_type"]}:
        bad.append(f"the build Fault detail must name the empty required fields: {out.get('detail')}")
    if "event_type" not in out.get("message", ""):
        bad.append(f"the build Fault message must name the empty field: {out.get('message')!r}")
    return bad


def _law_observe_fault():
    bad = []
    # observe_fault is the single fault constructor; its whole record is pinned (a law, because mutation
    # runs the laws, not the value cases): the reserved is_err tag true, and the code, message and detail
    # carried through verbatim.
    fault = HO.observe_fault("emit_failed", "the append failed; retry", {"error": "boom"})
    expected = {"is_err": True, "code": "emit_failed", "message": "the append failed; retry", "detail": {"error": "boom"}}
    if fault != expected:
        bad.append(f"observe_fault must build exactly the fault record: got {fault}")
    if not is_fault(fault):
        bad.append(f"observe_fault's record must be recognized by is_fault: {fault}")
    return bad


# --- the projection-handle builders (only the declared handle fields are fixed) --------------------


def _count_fold(state, event):
    return state + 1


def _law_declare_projection_handle():
    bad = []
    p = HO.declare_projection("open_orders", ["order.placed", "order.shipped"], _count_fold, 0)
    if is_fault(p):
        bad.append(f"declare_projection must return a Projection handle, not a Fault: {p}")
        return bad
    if p.get("projection_id") != "open_orders":
        bad.append(f"the handle must carry projection_id: {p.get('projection_id')!r}")
    if p.get("event_types") != ["order.placed", "order.shipped"]:
        bad.append(f"the handle must carry event_types: {p.get('event_types')!r}")
    # fold and initial_state are callables/seed, not stored in the serializable handle.
    if "fold" in p:
        bad.append("the Projection handle must not store the fold callable (it stays serializable)")
    return bad


def _law_build_snapshot_record():
    bad = []
    snap = HO.build_snapshot("open_orders", "eid-9", {"open": 3})
    if is_fault(snap):
        bad.append(f"build_snapshot must return a snapshot record, not a Fault: {snap}")
        return bad
    if snap.get("projection_id") != "open_orders":
        bad.append(f"the snapshot must carry projection_id: {snap}")
    if snap.get("snapshot_at") != "eid-9":
        bad.append(f"the snapshot must carry the log position snapshot_at: {snap}")
    if snap.get("state") != {"open": 3}:
        bad.append(f"the snapshot must carry the folded state: {snap}")
    return bad


def _law_resume_equals_replay():
    bad = []
    events = [{"event_type": "order.placed"}, {"event_type": "order.cancelled"}, {"event_type": "order.placed"}]
    # The filter lives in the Projection handle; apply_projection reads its event_types and invokes
    # matches, so the fold is a plain counter and the order.cancelled event is excluded by the filter.
    projection = {"projection_id": "p", "event_types": ["order.placed"]}

    def _count(state, event):
        return state + 1

    full = HO.apply_projection(projection, events, _count, 0)  # filters to 2 placed, counts them
    # A snapshot that folded the first two events (state 1) resumes over the tail (one placed) to 2.
    snap = HO.build_snapshot("p", "eid-2", 1)
    tail = [events[2]]
    resumed = HO.resume_from_snapshot(projection, snap, tail, _count)
    if full != 2:
        bad.append(f"apply_projection must filter by the handle's event_types and count 2 placed events: {full}")
    if resumed != 2:
        bad.append(f"resume_from_snapshot must equal a full replay (2), not change the answer: {resumed}")
    return bad


# --- otel_signal (the scenario fixes that the kind follows the type, not the exact shape) ----------


def _law_otel_signal_follows_type():
    bad = []
    # The whole signal is pinned per event type: the kind follows the dot-suffix through the declared
    # mapping, and an unlisted suffix falls to the explicit span_event terminal (not a mapped kind).
    # Multi-dot types check the suffix is the last segment. The attributes carry the type and id.
    cases = [
        ("hf.chain.started", "span_start"),
        ("hf.classify.completed", "metric"),
        ("hf.link.executed", "child_span"),
        ("hf.persist.query", "db_span"),
        ("hf.app.custom_thing", "span_event"),
    ]
    for event_type, kind in cases:
        signal = HO.otel_signal({"event_type": event_type, "event_id": "id-" + event_type})
        expected = {
            "kind": kind,
            "event_type": event_type,
            "attributes": {"hf.event_type": event_type, "hf.event_id": "id-" + event_type},
        }
        if signal != expected:
            bad.append(f"otel_signal for {event_type} must be exactly {expected}: got {signal}")
    # An event with no id carries an empty hf.event_id, not a missing key.
    no_id = HO.otel_signal({"event_type": "x.y"})
    if no_id.get("attributes", {}).get("hf.event_id") != "":
        bad.append(f"otel_signal must carry an empty hf.event_id when the event has none: {no_id}")
    return bad


# --- compute_metric (plain metric: the fold result is fixed; grouped shape is a gap) ---------------


def _law_compute_metric_plain():
    bad = []

    def _count(state, event):
        return state + 1

    metric = {"name": "order_count", "event_types": ["order.placed"], "fold": _count, "initial": 0}
    events = [{"event_type": "order.placed"}, {"event_type": "order.placed"}, {"event_type": "order.placed"}]
    out = HO.compute_metric(metric, events)
    if out != 3:
        bad.append(f"compute_metric must fold the source events to one number for a plain metric: {out}")
    return bad


def _law_compute_metric_grouped():
    bad = []

    def _count(state, event):
        return state + 1

    # A grouped metric carries a group function; compute_metric folds each group separately and keeps
    # only the events whose type is in event_types (the "other" event below is excluded, so a=2 not 3).
    metric = {"name": "per_link", "event_types": ["link.executed"], "fold": _count, "initial": 0, "group": lambda event: event["link"]}
    events = [
        {"event_type": "link.executed", "link": "a"},
        {"event_type": "link.executed", "link": "a"},
        {"event_type": "link.executed", "link": "b"},
        {"event_type": "other", "link": "a"},
    ]
    out = HO.compute_metric(metric, events)
    if out != {"a": 2, "b": 1}:
        bad.append(f"compute_metric grouped must map each group key to its value, filtering by event_types: {out}")
    return bad


# --- threshold_projection / evaluate_threshold (the ThresholdProjection record and the firing decision) ---


def _law_threshold_projection_handle():
    bad = []
    t = HO.threshold_projection("t1", "fault_rate", {"gt": 0.1}, "5m", "10m", {"to": "ops"}, True)
    if is_fault(t):
        bad.append(f"threshold_projection must return a ThresholdProjection, not a Fault: {t}")
        return bad
    # Every field is fixed, so a dropped or swapped field is caught.
    expected = {"projection_id": "t1", "metric": "fault_rate", "condition": {"gt": 0.1},
                "window": "5m", "cooldown": "10m", "alert": {"to": "ops"}, "enabled": True}
    for key, value in expected.items():
        if t.get(key) != value:
            bad.append(f"the ThresholdProjection must carry {key}={value!r}, got {t.get(key)!r}")
    return bad


def _count_fold_fixture(state, event):
    return state + 1


def _threshold(condition):
    """A ThresholdProjection watching a plain count metric with the given condition."""
    return HO.threshold_projection("p", "c", condition, "5m", "10m", {}, True)


def _law_evaluate_threshold_plain():
    bad = []
    metric = {"name": "c", "event_types": ["x"], "fold": _count_fold_fixture, "initial": 0}
    two = [{"event_type": "x"}, {"event_type": "x"}]  # the metric value is 2
    # Each comparator on value 2, including the boundary that separates gt from ge and lt from le, and
    # an operator the table does not name, which must resolve to the non-firing terminal, not a hit.
    checks = [
        ({"gt": 1}, True), ({"gt": 2}, False),
        ({"ge": 2}, True), ({"ge": 3}, False),
        ({"lt": 3}, True), ({"lt": 2}, False),
        ({"le": 2}, True), ({"le": 1}, False),
        ({"eq": 2}, True), ({"eq": 3}, False),
        ({"unknown_op": 2}, False),
    ]
    for condition, expected in checks:
        got = HO.evaluate_threshold(_threshold(condition), metric, two)
        if got is not expected:
            bad.append(f"evaluate_threshold plain {condition} on value 2 must be {expected}, got {got!r}")
    return bad


def _law_evaluate_threshold_grouped():
    bad = []
    metric = {"name": "per_link", "event_types": ["link.executed"], "fold": _count_fold_fixture,
              "initial": 0, "group": lambda event: event["link"]}
    events = [
        {"event_type": "link.executed", "link": "a"},
        {"event_type": "link.executed", "link": "a"},
        {"event_type": "link.executed", "link": "b"},
    ]
    t = HO.threshold_projection("g", "per_link", {"gt": 1}, "5m", "10m", {}, True)
    decision = HO.evaluate_threshold(t, metric, events)
    if not isinstance(decision, dict) or set(decision) != {"fired", "firings"}:
        bad.append(f"grouped evaluate_threshold must return exactly {{fired, firings}}: {decision}")
        return bad
    if decision["fired"] is not True:
        bad.append(f"grouped fired must be True when any group crosses: {decision}")
    firings = {f["group"]: f for f in decision["firings"]}
    if set(firings) != {"a", "b"}:
        bad.append(f"firings must carry one record per group: {decision}")
        return bad
    if firings["a"]["fired"] is not True or firings["a"]["value"] != 2:
        bad.append(f"group a (value 2 gt 1) must fire: {firings['a']}")
    if firings["b"]["fired"] is not False or firings["b"]["value"] != 1:
        bad.append(f"group b (value 1 gt 1) must not fire: {firings['b']}")
    return bad


# --- hlc (the advance rules are fixed; the dict key names are a gap, so assert via read-back) -------


def _law_hlc_send_rules():
    bad = []
    # Each outcome is pinned to the whole HLC dict, so the physical max, the reset-vs-increment of the
    # logical counter, and the carried source are all caught.
    # physical_now ahead: physical advances, logical resets to 0.
    advanced = HO.hlc_send({"physical": 5, "logical": 3, "source": "a"}, 9)
    if advanced != {"physical": 9, "logical": 0, "source": "a"}:
        bad.append(f"hlc_send must advance physical and reset logical to 0: got {advanced}")
    # tie (physical_now == local): physical stays, logical increments.
    tied = HO.hlc_send({"physical": 9, "logical": 3, "source": "a"}, 9)
    if tied != {"physical": 9, "logical": 4, "source": "a"}:
        bad.append(f"hlc_send must keep physical and increment logical on a tie: got {tied}")
    # physical_now behind local: physical stays local's, and that is not an advance, so logical increments.
    behind = HO.hlc_send({"physical": 9, "logical": 3, "source": "a"}, 5)
    if behind != {"physical": 9, "logical": 4, "source": "a"}:
        bad.append(f"hlc_send must keep local physical and increment logical when physical_now is behind: got {behind}")
    return bad


def _law_hlc_receive_rules():
    bad = []
    # physical is the max of the three; the logical counter is read from the closed four-row table keyed
    # by which clocks already held that winning physical. Each of the four rows is pinned to the whole
    # resulting HLC dict, and the source is always the receiver's.
    # neither held it (physical_now wins): logical starts at 0.
    now_wins = HO.hlc_receive({"physical": 5, "logical": 2, "source": "a"}, {"physical": 7, "logical": 5, "source": "b"}, 9)
    if now_wins != {"physical": 9, "logical": 0, "source": "a"}:
        bad.append(f"hlc_receive: when physical_now wins, logical starts at 0: got {now_wins}")
    # only local held it: one past local's logical.
    local_wins = HO.hlc_receive({"physical": 9, "logical": 2, "source": "a"}, {"physical": 7, "logical": 5, "source": "b"}, 3)
    if local_wins != {"physical": 9, "logical": 3, "source": "a"}:
        bad.append(f"hlc_receive: when only local held the physical, logical is local+1: got {local_wins}")
    # only incoming held it: one past incoming's logical.
    incoming_wins = HO.hlc_receive({"physical": 7, "logical": 2, "source": "a"}, {"physical": 9, "logical": 5, "source": "b"}, 3)
    if incoming_wins != {"physical": 9, "logical": 6, "source": "a"}:
        bad.append(f"hlc_receive: when only incoming held the physical, logical is incoming+1: got {incoming_wins}")
    # both held it: one past the larger logical.
    both_held = HO.hlc_receive({"physical": 9, "logical": 2, "source": "a"}, {"physical": 9, "logical": 5, "source": "b"}, 3)
    if both_held != {"physical": 9, "logical": 6, "source": "a"}:
        bad.append(f"hlc_receive: when both held the physical, logical is max(local,incoming)+1: got {both_held}")
    return bad


# --- identity (the canonical id and the surfaced conflict are fixed; key format is a gap) ----------


def _law_fold_identity_and_resolve():
    bad = []
    claim_a = {"event_type": "identity.claimed", "payload": {"external_system": "github", "external_id": "gh-1", "canonical_id": "c1"}}
    bindings = HO.fold_identity_claims([claim_a])
    if is_fault(bindings):
        bad.append(f"fold_identity_claims is pure and returns bindings, not a fault: {bindings}")
        return bad
    # resolve_identity on the table fold_identity_claims produced returns the canonical id.
    got = HO.resolve_identity("gh-1", "github", bindings)
    if got != "c1":
        bad.append(f"resolve_identity must return the canonical id for a bound external id: {got!r}")
    # An unresolvable id is a bounded absence, NOTHING, never a fault.
    absent = HO.resolve_identity("gh-unknown", "github", bindings)
    if absent is not HO.NOTHING:
        bad.append(f"an unresolvable id must return NOTHING, not {absent!r}")
    if is_fault(absent):
        bad.append("NOTHING must never be recognized by is_fault (disjoint from a Fault)")
    return bad


def _claim(canonical_id):
    return {"event_type": "identity.claimed",
            "payload": {"external_system": "github", "external_id": "gh-1", "canonical_id": canonical_id}}


def _law_fold_identity_conflict_surfaced():
    bad = []
    # Every merge case is pinned to its exact folded value, so a dropped record key, a nested instead
    # of flat candidate list, or a lost dedup is caught rather than hidden behind a loose "both ids
    # appear somewhere" check.
    fresh = HO.fold_identity_claims([_claim("c1")])
    key = next(iter(fresh))
    if fresh[key] != "c1":
        bad.append(f"a first claim must bind the external id to its canonical id as a bare scalar: {fresh}")
    # same: re-claiming the same canonical id leaves the binding unchanged, not a conflict.
    same = HO.fold_identity_claims([_claim("c1"), _claim("c1")])
    if same[key] != "c1":
        bad.append(f"re-claiming the same canonical id must leave the binding unchanged: {same}")
    # diverging: a differing second id turns the binding into a flat conflict record carrying both.
    diverging = HO.fold_identity_claims([_claim("c1"), _claim("c2")])
    if diverging[key] != {"conflict": True, "candidates": ["c1", "c2"]}:
        bad.append(f"a differing claim must surface a flat conflict record carrying both ids: {diverging[key]}")
    # conflicting: a third differing id appends to the standing conflict's candidates, flat not nested.
    three = HO.fold_identity_claims([_claim("c1"), _claim("c2"), _claim("c3")])
    if three[key] != {"conflict": True, "candidates": ["c1", "c2", "c3"]}:
        bad.append(f"a third differing claim must append to the flat candidates list: {three[key]}")
    # dedup: re-claiming an id already among the candidates must not duplicate it.
    dedup = HO.fold_identity_claims([_claim("c1"), _claim("c2"), _claim("c2")])
    if dedup[key] != {"conflict": True, "candidates": ["c1", "c2"]}:
        bad.append(f"re-claiming a candidate already present must not duplicate it: {dedup[key]}")
    # a conflicted binding is unresolved: resolve returns NOTHING, never one of the candidates.
    if HO.resolve_identity("gh-1", "github", diverging) is not HO.NOTHING:
        bad.append("resolve_identity on a conflicted binding must return NOTHING, not a candidate")
    return bad


# --- request_canonical (the join key is fixed; the full field layout is a gap) ---------------------


def _law_request_canonical_keyed_by_request_id():
    bad = []
    event = HO.request_canonical(
        "req-1", "GET", "/orders", 200, "u1", "s1", "place_order", 3, ["validate", "persist"],
        5, 0, 2, 1000, "ok", "", "", 2000,
    )
    if is_fault(event):
        bad.append(f"request_canonical is pure and returns an Event, not a fault: {event}")
        return bad
    # The whole dense event is pinned: it is the hf.request.completed envelope keyed by request_id (the
    # join key), the auth partition carrying caller and session, and the payload colocating every HTTP,
    # chain, intake, persistence and outcome fact. Pinning the whole value catches a dropped or renamed
    # field key, a mis-keyed aggregate, or a wrong sequence.
    expected = {
        "event_id": "req-1",
        "event_type": "hf.request.completed",
        "event_version": "1.0",
        "timestamp": "",
        "sequence": 0,
        "aggregate_type": "request",
        "aggregate_id": "req-1",
        "payload": {
            "request_id": "req-1", "http_method": "GET", "http_path": "/orders", "http_status": 200,
            "chain_name": "place_order", "link_count": 3, "link_sequence": ["validate", "persist"],
            "token_count": 5, "rejection_count": 0, "query_count": 2, "query_duration_ns": 1000,
            "result": "ok", "fault_code": "", "fault_category": "", "duration_ns": 2000,
        },
        "auth": {"caller_id": "u1", "session_id": "s1"},
        "meta": {},
    }
    if event != expected:
        bad.append(f"request_canonical must assemble the one declared canonical event exactly: got {event}")
    return bad


# --- event_log_schema (the table and the named indexes are fixed) ---------------------------------


def _law_event_log_schema():
    bad = []
    manifest = HO.event_log_schema()
    if is_fault(manifest):
        bad.append(f"event_log_schema is pure and returns the manifest, not a fault: {manifest}")
        return bad
    # The whole manifest is a fixed declared shape, so every field is pinned exactly: the table name,
    # the envelope columns in order, the four projection-filter indexes with their names and columns,
    # and the append_only mark honest-persist reads to reject update and delete. Pinning the whole
    # value is what lets a dropped column name, a renamed index, or a flipped append_only be caught.
    expected = {
        "table": "honest_event_log",
        "columns": ["event_id", "event_type", "event_version", "timestamp", "sequence",
                    "aggregate_type", "aggregate_id", "payload", "auth", "meta"],
        "indexes": [
            {"name": "ix_event_log_event_type", "columns": ["event_type"]},
            {"name": "ix_event_log_aggregate", "columns": ["aggregate_type", "aggregate_id"]},
            {"name": "ix_event_log_timestamp", "columns": ["timestamp"]},
            {"name": "ix_event_log_aggregate_sequence", "columns": ["aggregate_id", "sequence"]},
        ],
        "append_only": True,
    }
    if manifest != expected:
        bad.append(f"the event-log manifest must be the one declared shape exactly: got {manifest}")
    return bad


_LAWS = {
    "new_event_id": _law_new_event_id,
    "event_timestamp": _law_event_timestamp,
    "next_sequence": _law_next_sequence,
    "append_event_appends_one": _law_append_event_appends_one,
    "append_event_serializes_maps_as_json": _law_append_event_serializes_maps_as_json,
    "append_event_failure_outcome": _law_append_event_failure_outcome,
    "run_emit_appends_and_returns_event": _law_run_emit_appends_and_returns_event,
    "run_emit_append_failure_builds_fault": _law_run_emit_append_failure_builds_fault,
    "run_emit_sequence_increases": _law_run_emit_sequence_increases,
    "run_emit_empty_required_field": _law_run_emit_empty_required_field_faults_and_writes_nothing,
    "emit_delegates_to_run_emit": _law_emit_delegates_to_run_emit,
    "build_event_empty_required_field": _law_build_event_empty_required_field,
    "observe_fault": _law_observe_fault,
    "declare_projection_handle": _law_declare_projection_handle,
    "build_snapshot_record": _law_build_snapshot_record,
    "resume_equals_replay": _law_resume_equals_replay,
    "otel_signal_follows_type": _law_otel_signal_follows_type,
    "compute_metric_plain": _law_compute_metric_plain,
    "compute_metric_grouped": _law_compute_metric_grouped,
    "threshold_projection_handle": _law_threshold_projection_handle,
    "evaluate_threshold_plain": _law_evaluate_threshold_plain,
    "evaluate_threshold_grouped": _law_evaluate_threshold_grouped,
    "hlc_send_rules": _law_hlc_send_rules,
    "hlc_receive_rules": _law_hlc_receive_rules,
    "fold_identity_and_resolve": _law_fold_identity_and_resolve,
    "fold_identity_conflict_surfaced": _law_fold_identity_conflict_surfaced,
    "request_canonical_keyed_by_request_id": _law_request_canonical_keyed_by_request_id,
    "event_log_schema": _law_event_log_schema,
}


def run():
    failed = {}
    for name, law in _LAWS.items():
        try:
            msgs = law()
        except Exception as exc:
            msgs = [f"law raised {type(exc).__name__}: {exc}"]
        if msgs:
            failed[name] = msgs
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HO-law [{name}]: {msgs}")
    print(f"HO laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(run())
