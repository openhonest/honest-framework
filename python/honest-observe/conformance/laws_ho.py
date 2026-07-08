"""honest-observe conformance: the generative proof (the behavioural circle).

What a data file cannot express is proved here: the envelope's auth/meta attachment and
validation branches, the auth/meta extraction, the projection filter predicate across every
filter, the fold itself (a function), and the async emit boundary driven through a stand-in
runtime. Each probe returns a list of failures; run() aggregates.
"""

import asyncio

from honest_observe import apply_projection, build_event, emit, extract_auth, extract_meta, matches

# A complete, valid set of envelope arguments — probes vary one thing at a time off this base.
_BASE = {
    "event_type": "hf.chain.completed",
    "event_version": "1.0",
    "aggregate_type": "chain",
    "aggregate_id": "create_user",
    "payload": {"result": "ok"},
    "event_id": "019x2k",
    "timestamp": "2026-03-15T14:23:07.441832Z",
    "sequence": 0,
}


def _probe_build_event():
    """Envelope assembly + validation (§2): required-field check, and auth/meta attached only
    when supplied. sequence=0 and an empty payload are valid (not treated as missing)."""
    bad = []

    # Valid, no auth/meta -> those keys are absent; sequence 0 is kept.
    result = build_event(**_BASE)
    if "ok" not in result:
        bad.append(f"a complete event should be ok: {result}")
    else:
        event = result["ok"]
        if "auth" in event or "meta" in event:
            bad.append("auth/meta must be absent when not supplied")
        if event["sequence"] != 0 or event["payload"] != {"result": "ok"}:
            bad.append("sequence 0 / payload should be carried verbatim")

    # auth supplied, meta not -> auth present, meta absent.
    result = build_event(**_BASE, auth={"caller_id": "u1"})
    if result["ok"].get("auth") != {"caller_id": "u1"} or "meta" in result["ok"]:
        bad.append("auth should attach, meta should stay absent")

    # both supplied.
    result = build_event(**_BASE, auth={"caller_id": "u1"}, meta={"release": "r1"})
    if result["ok"].get("meta") != {"release": "r1"}:
        bad.append("meta should attach when supplied")

    # empty required field (event_type) -> invalid_event naming it; the full fault is pinned.
    result = build_event(**{**_BASE, "event_type": ""})
    if result != {"err": {"code": "invalid_event", "message": "Event is missing required field(s): ['event_type']", "category": "server", "detail": {"missing": ["event_type"]}}}:
        bad.append(f"an empty required field should fault invalid_event in full: {result}")

    # an empty aggregate_id is also caught (a different required field).
    if build_event(**{**_BASE, "aggregate_id": ""}).get("err", {}).get("code") != "invalid_event":
        bad.append("an empty aggregate_id should fault")
    return bad


def _probe_extract():
    """Auth/meta extraction (§2.2, §2.3): the configured fields present in context, or None."""
    bad = []
    context = {"caller_id": "u1", "session": "s1", "release": "r1", "other": "x"}

    if extract_auth(context, ["caller_id", "session", "missing"]) != {"caller_id": "u1", "session": "s1"}:
        bad.append("extract_auth should pull the present configured fields, in order")
    if extract_auth(context, ["nope"]) is not None:
        bad.append("extract_auth with no present field should be None")
    if extract_meta(context, ["release", "absent"]) != {"release": "r1"}:
        bad.append("extract_meta should pull the present configured fields")
    if extract_meta(context, []) is not None:
        bad.append("extract_meta with no fields should be None")
    return bad


def _probe_matches():
    """The projection filter predicate (§6.1): each filter, the half-open time window, and the
    all-pass case."""
    bad = []
    event = {"event_type": "a.b", "aggregate_type": "order", "aggregate_id": "o1", "timestamp": "2026-03-15T12:00:00Z"}

    checks = [
        ("no filters", matches(event), True),
        ("type miss", matches(event, event_types=["x.y"]), False),
        ("type hit + agg-type miss", matches(event, event_types=["a.b"], aggregate_type="user"), False),
        ("agg-id miss", matches(event, aggregate_id="o2"), False),
        ("before window", matches(event, from_ts="2026-03-16T00:00:00Z"), False),
        ("at/after to (exclusive)", matches(event, to_ts="2026-03-15T12:00:00Z"), False),
        ("all constraints pass", matches(event, event_types=["a.b"], aggregate_type="order", aggregate_id="o1", from_ts="2026-03-15T00:00:00Z", to_ts="2026-03-16T00:00:00Z"), True),
    ]
    for label, got, want in checks:
        if got != want:
            bad.append(f"matches({label}) should be {want}, got {got}")
    return bad


def _probe_projection():
    """The fold over filtered events (§6): only matching events fold; an empty log yields the
    initial state unchanged."""
    bad = []
    events = [
        {"event_type": "click", "aggregate_type": "ui", "aggregate_id": "p1", "timestamp": "2026-01-01T00:00:00Z", "payload": {"n": 1}},
        {"event_type": "click", "aggregate_type": "ui", "aggregate_id": "p1", "timestamp": "2026-01-02T00:00:00Z", "payload": {"n": 2}},
        {"event_type": "view", "aggregate_type": "ui", "aggregate_id": "p1", "timestamp": "2026-01-03T00:00:00Z", "payload": {"n": 99}},
    ]

    def fold(state, event):
        return {"sum": state["sum"] + event["payload"]["n"], "count": state["count"] + 1}

    # Only the two click events fold; the view is filtered out.
    result = apply_projection(events, fold, {"sum": 0, "count": 0}, event_types=["click"])
    if result != {"sum": 3, "count": 2}:
        bad.append(f"projection should fold only matching events: {result}")

    # No filter -> every event folds.
    if apply_projection(events, fold, {"sum": 0, "count": 0})["count"] != 3:
        bad.append("an unfiltered projection should fold every event")

    # from_ts excludes events strictly before it; an event AT from_ts is included (pins the < boundary).
    from_boundary = apply_projection(events, fold, {"sum": 0, "count": 0}, from_ts="2026-01-02T00:00:00Z")
    if from_boundary["count"] != 2:
        bad.append(f"from_ts should include an event at the boundary (>= from_ts): {from_boundary}")

    # Empty log -> initial state, untouched.
    if apply_projection([], fold, {"sum": 0, "count": 0}) != {"sum": 0, "count": 0}:
        bad.append("an empty log should return the initial state")
    return bad


class _Runtime:
    """A stand-in emit runtime (§3): canned id/timestamp/sequence/version, configured auth/meta
    field names, an append that succeeds or fails, recording what it was handed."""

    def __init__(self, append_ok=True, auth_fields=(), meta_fields=()):
        self._append_ok = append_ok
        self.auth_fields = list(auth_fields)
        self.meta_fields = list(meta_fields)
        self.appended = []

    def event_id(self):
        return "019x2k"

    def timestamp(self):
        return "2026-03-15T14:23:07.441832Z"

    def sequence(self, aggregate_id):
        return 7

    def version(self, event_type):
        return "1.0"

    async def append(self, event):
        self.appended.append(event)
        if self._append_ok:
            return {"ok": {}}
        return {"err": {"code": "log_write_failed", "message": "boom", "category": "server", "detail": None}}


def _probe_emit():
    """The emit boundary (§3): assemble through the runtime and append. Success returns the
    event_id and appends a complete envelope (id/version/sequence from the runtime, auth/meta from
    context); a malformed envelope returns its validation fault and writes nothing; an append
    failure becomes emit_failed."""

    async def _run():
        bad = []
        context = {"caller_id": "u1", "release": "r1", "other": "x"}

        # Success: ok(event_id); the appended envelope carries the runtime's values and the
        # auth/meta pulled from context by the configured field names.
        rt = _Runtime(auth_fields=["caller_id"], meta_fields=["release"])
        result = await emit("hf.chain.completed", "chain", "c1", {"result": "ok"}, context, rt)
        if result != {"ok": {"event_id": "019x2k"}}:
            bad.append(f"successful emit should return the event_id: {result}")
        elif len(rt.appended) != 1:
            bad.append("a successful emit should append exactly one event")
        else:
            event = rt.appended[0]
            if event["event_version"] != "1.0" or event["sequence"] != 7 or event["event_type"] != "hf.chain.completed":
                bad.append(f"appended envelope wrong: {event}")
            if event.get("auth") != {"caller_id": "u1"} or event.get("meta") != {"release": "r1"}:
                bad.append(f"emit should attach auth/meta from context: {event.get('auth')} {event.get('meta')}")

        # No configured auth/meta fields -> those keys are absent on the appended event.
        rt2 = _Runtime()
        await emit("hf.chain.completed", "chain", "c1", {}, context, rt2)
        if "auth" in rt2.appended[0] or "meta" in rt2.appended[0]:
            bad.append("with no configured fields, auth/meta must be absent")

        # Malformed envelope (empty aggregate_id) -> validation fault, nothing appended.
        rt3 = _Runtime()
        bad_result = await emit("hf.chain.completed", "chain", "", {}, context, rt3)
        if bad_result.get("err", {}).get("code") != "invalid_event":
            bad.append(f"an empty required field should return invalid_event: {bad_result}")
        if rt3.appended:
            bad.append("a malformed envelope must not be appended")

        # Append failure -> emit_failed wrapping the cause.
        rt4 = _Runtime(append_ok=False)
        failed = await emit("hf.chain.completed", "chain", "c1", {}, context, rt4)
        if failed != {"err": {"code": "emit_failed", "message": "Failed to append event to the log", "category": "server", "detail": {"cause": {"code": "log_write_failed", "message": "boom", "category": "server", "detail": None}}}}:
            bad.append(f"an append failure should become emit_failed wrapping the cause in full: {failed}")
        return bad

    return asyncio.run(_run())


def _probe_framework_events():
    """The framework event catalogue (section 4.1-4.4): pure builders for chain, link, classification,
    and state-machine events, each returning {event_type, aggregate_type, aggregate_id, payload}."""
    from honest_observe import (
        chain_completed,
        chain_started,
        classify_completed,
        link_executed,
        link_faulted,
        state_rejected,
        state_transitioned,
    )

    bad = []
    # Each builder's full {event_type, aggregate_type, aggregate_id, payload} dict is pinned exactly, so
    # every key and value (and the presence/absence of each optional field) is caught.
    builders = [
        (chain_started("checkout", 3, ["order_id", "items"]),
         {"event_type": "hf.chain.started", "aggregate_type": "chain", "aggregate_id": "checkout", "payload": {"chain_name": "checkout", "link_count": 3, "input_types": ["order_id", "items"]}}),
        (chain_completed("checkout", 3, 1500, "ok"),
         {"event_type": "hf.chain.completed", "aggregate_type": "chain", "aggregate_id": "checkout", "payload": {"chain_name": "checkout", "duration_ns": 1500, "link_count": 3, "result": "ok"}}),
        (chain_completed("checkout", 3, 1500, "err", fault_code="invalid_email", fault_category="client"),
         {"event_type": "hf.chain.completed", "aggregate_type": "chain", "aggregate_id": "checkout", "payload": {"chain_name": "checkout", "duration_ns": 1500, "link_count": 3, "result": "err", "fault_code": "invalid_email", "fault_category": "client"}}),
        (link_executed("validate", "checkout", 200, "ok", boundary=False, mutations=0, singletons=0, nondeterminism=False, io_calls=0),
         {"event_type": "hf.link.executed", "aggregate_type": "link", "aggregate_id": "validate", "payload": {"link_name": "validate", "chain_name": "checkout", "duration_ns": 200, "result": "ok", "boundary": False, "mutations": 0, "singletons": 0, "nondeterminism": False, "io_calls": 0}}),
        (link_executed("validate", "checkout", 200, "err", boundary=True, mutations=1, singletons=2, nondeterminism=True, io_calls=3, fault_code="bad"),
         {"event_type": "hf.link.executed", "aggregate_type": "link", "aggregate_id": "validate", "payload": {"link_name": "validate", "chain_name": "checkout", "duration_ns": 200, "result": "err", "boundary": True, "mutations": 1, "singletons": 2, "nondeterminism": True, "io_calls": 3, "fault_code": "bad"}}),
        (link_faulted("validate", "checkout", "invalid_email", "client", "Bad email"),
         {"event_type": "hf.link.faulted", "aggregate_type": "link", "aggregate_id": "validate", "payload": {"link_name": "validate", "chain_name": "checkout", "fault_code": "invalid_email", "fault_category": "client", "fault_message": "Bad email"}}),
        (link_faulted("validate", "checkout", "invalid_email", "client", "Bad email", input_manifest={"email": "x"}),
         {"event_type": "hf.link.faulted", "aggregate_type": "link", "aggregate_id": "validate", "payload": {"link_name": "validate", "chain_name": "checkout", "fault_code": "invalid_email", "fault_category": "client", "fault_message": "Bad email", "input_manifest": {"email": "x"}}}),
        (classify_completed("order_vocab", 5, 1, 300, {"unrecognized": 1}),
         {"event_type": "hf.classify.completed", "aggregate_type": "classify", "aggregate_id": "order_vocab", "payload": {"vocabulary_name": "order_vocab", "token_count": 5, "rejection_count": 1, "duration_ns": 300, "rejection_reasons": {"unrecognized": 1}}}),
        (state_transitioned("order_sm", "o1", "pending", "pay", "paid", 400),
         {"event_type": "hf.state.transitioned", "aggregate_type": "state_machine", "aggregate_id": "order_sm:o1", "payload": {"machine_name": "order_sm", "entity_id": "o1", "from_state": "pending", "event": "pay", "to_state": "paid", "duration_ns": 400}}),
        (state_rejected("order_sm", "o1", "paid", "pay", "no_transition"),
         {"event_type": "hf.state.rejected", "aggregate_type": "state_machine", "aggregate_id": "order_sm:o1", "payload": {"machine_name": "order_sm", "entity_id": "o1", "current_state": "paid", "event": "pay", "fault_code": "no_transition"}}),
    ]
    for actual, expected in builders:
        if actual != expected:
            bad.append(f"framework event builder mismatch: got {actual}, expected {expected}")
    return bad


def _probe_canonical_app_events():
    """The canonical request event (section 4.6) and application lifecycle events (section 4.7): pure
    builders, with optional identity/chain/fault and release/traceback fields present only when set."""
    from honest_observe import app_error, app_started, app_stopped, link_summary, request_canonical

    bad = []
    # Full-dict equality per builder, so every key/value and each optional field's presence is pinned.
    builders = [
        (link_summary("validate", 200, "ok"),
         {"link_name": "validate", "duration_ns": 200, "result": "ok"}),
        (link_summary("pay", 50, "err", fault_code="declined"),
         {"link_name": "pay", "duration_ns": 50, "result": "err", "fault_code": "declined"}),
        (request_canonical("req-1", "POST", "/api/orders", 200, 2, [link_summary("validate", 200, "ok")], 3, 0, 4, 9000, "ok", 12000, caller_id="u1", chain_name="checkout"),
         {"event_type": "hf.request.canonical", "aggregate_type": "request", "aggregate_id": "req-1", "payload": {"http_method": "POST", "http_path": "/api/orders", "http_status": 200, "link_count": 2, "link_sequence": [{"link_name": "validate", "duration_ns": 200, "result": "ok"}], "token_count": 3, "rejection_count": 0, "query_count": 4, "query_duration_ns": 9000, "result": "ok", "duration_ns": 12000, "request_id": "req-1", "source": "server", "caller_id": "u1", "chain_name": "checkout"}}),
        (request_canonical("req-2", "GET", "/x", 500, 0, [], 0, 0, 0, 0, "err", 5, fault_code="boom", fault_category="server"),
         {"event_type": "hf.request.canonical", "aggregate_type": "request", "aggregate_id": "req-2", "payload": {"http_method": "GET", "http_path": "/x", "http_status": 500, "link_count": 0, "link_sequence": [], "token_count": 0, "rejection_count": 0, "query_count": 0, "query_duration_ns": 0, "result": "err", "duration_ns": 5, "request_id": "req-2", "source": "server", "fault_code": "boom", "fault_category": "server"}}),
        (request_canonical("req-3", "PUT", "/y", 201, 1, [], 2, 0, 1, 100, "ok", 300, session_id="sess-9"),
         {"event_type": "hf.request.canonical", "aggregate_type": "request", "aggregate_id": "req-3", "payload": {"http_method": "PUT", "http_path": "/y", "http_status": 201, "link_count": 1, "link_sequence": [], "token_count": 2, "rejection_count": 0, "query_count": 1, "query_duration_ns": 100, "result": "ok", "duration_ns": 300, "request_id": "req-3", "source": "server", "session_id": "sess-9"}}),
        (app_started("shop", "production", 5, 12, 3, release="r1"),
         {"event_type": "hf.app.started", "aggregate_type": "app", "aggregate_id": "shop", "payload": {"app_name": "shop", "environment": "production", "chains_loaded": 5, "links_loaded": 12, "vocabs_loaded": 3, "release": "r1"}}),
        (app_started("shop", "dev", 1, 1, 1),
         {"event_type": "hf.app.started", "aggregate_type": "app", "aggregate_id": "shop", "payload": {"app_name": "shop", "environment": "dev", "chains_loaded": 1, "links_loaded": 1, "vocabs_loaded": 1}}),
        (app_stopped("shop", 60000, "graceful"),
         {"event_type": "hf.app.stopped", "aggregate_type": "app", "aggregate_id": "shop", "payload": {"app_name": "shop", "uptime_ns": 60000, "reason": "graceful"}}),
        (app_error("shop", "ValueError", "boom", traceback="tb", context="startup"),
         {"event_type": "hf.app.error", "aggregate_type": "app", "aggregate_id": "shop", "payload": {"error_type": "ValueError", "message": "boom", "traceback": "tb", "context": "startup"}}),
        (app_error("shop", "ValueError", "boom"),
         {"event_type": "hf.app.error", "aggregate_type": "app", "aggregate_id": "shop", "payload": {"error_type": "ValueError", "message": "boom"}}),
    ]
    for actual, expected in builders:
        if actual != expected:
            bad.append(f"canonical/app event builder mismatch: got {actual}, expected {expected}")
    return bad


def _probe_event_log():
    """The event-log table (section 10): observe owns the honest_event_log definition as pure data — the
    persist-compatible schema (ten columns matching the envelope, four projection indexes) and the
    append-only manifest that wraps it. observe never imports persist; persist applies this dict."""
    from honest_observe import event_log_manifest, event_log_schema

    bad = []
    # The full schema dict is pinned exactly: ten columns in envelope order with their types and
    # nullability (the seven framework fields plus the JSON payload NOT NULL, auth/meta nullable),
    # the primary key, and the four projection indexes over their declared columns.
    expected_table = {
        "columns": {
            "event_id": {"type": "text", "primary_key": True, "nullable": False},
            "event_type": {"type": "text", "nullable": False},
            "event_version": {"type": "text", "nullable": False},
            "timestamp": {"type": "text", "nullable": False},
            "sequence": {"type": "integer", "nullable": False},
            "aggregate_type": {"type": "text", "nullable": False},
            "aggregate_id": {"type": "text", "nullable": False},
            "payload": {"type": "text", "nullable": False},
            "auth": {"type": "text", "nullable": True},
            "meta": {"type": "text", "nullable": True},
        },
        "primary_key": ["event_id"],
        "indexes": {
            "idx_event_type": {"columns": ["event_type"]},
            "idx_aggregate": {"columns": ["aggregate_type", "aggregate_id"]},
            "idx_timestamp": {"columns": ["timestamp"]},
            "idx_sequence": {"columns": ["aggregate_id", "sequence"]},
        },
    }
    schema = event_log_schema()
    if schema != {"honest_event_log": expected_table}:
        bad.append(f"event_log_schema wrong: {schema}")
    if event_log_manifest() != {"table": "honest_event_log", "append_only": True, "schema": expected_table}:
        bad.append(f"event_log_manifest wrong: {event_log_manifest()}")
    return bad


def _probe_snapshot():
    """Snapshot projections (section 6.3): a snapshot record, the snapshot-interval decision, the
    declared-projection API, and the resume that replays only the events after a snapshot onto its
    state rather than from the beginning. All pure; persisting/loading the snapshot is the boundary's."""
    from honest_observe import build_snapshot, declare_projection, resume_from_snapshot, should_snapshot

    bad = []

    # The snapshot record is exactly the three documented fields.
    snap = build_snapshot("sub_summary", "2026-03-15T00:00:00Z", {"count": 1000})
    if snap != {"projection_id": "sub_summary", "snapshot_at": "2026-03-15T00:00:00Z", "state": {"count": 1000}}:
        bad.append(f"build_snapshot wrong: {snap}")

    # should_snapshot: take one once the interval is reached; never when there is no interval.
    if should_snapshot(1000, 1000) is not True or should_snapshot(1500, 1000) is not True:
        bad.append("should_snapshot should fire at or past the interval")
    if should_snapshot(999, 1000) is not False:
        bad.append("should_snapshot should not fire below the interval")
    if should_snapshot(1, 1) is not True:
        bad.append("should_snapshot should fire at an interval of 1 (pins the > 0 positive-interval check)")
    if should_snapshot(5000, None) is not False or should_snapshot(5000, 0) is not False:
        bad.append("should_snapshot should never fire without a positive interval")

    # A counting fold over the post-snapshot events.
    def fold(state, event):
        return {"count": state["count"] + 1}

    events = [
        {"event_type": "app.x", "aggregate_type": "a", "aggregate_id": "1", "timestamp": "2026-03-15T00:00:00Z"},  # at snapshot — already counted
        {"event_type": "app.x", "aggregate_type": "a", "aggregate_id": "1", "timestamp": "2026-03-15T01:00:00Z"},  # after
        {"event_type": "app.y", "aggregate_type": "a", "aggregate_id": "1", "timestamp": "2026-03-15T02:00:00Z"},  # after, filtered out
    ]
    # Resume from the snapshot: only strictly-later events fold, the type filter still applies, and the
    # starting state is the snapshot's — so the count continues from 1000, not from zero.
    resumed = resume_from_snapshot(snap, events, fold, event_types=["app.x"])
    if resumed != {"count": 1001}:
        bad.append(f"resume_from_snapshot should fold only later, matching events onto the snapshot state: {resumed}")
    # No snapshot_at boundary skipped: an event exactly at snapshot_at is treated as already-included.
    only_at = resume_from_snapshot(snap, [events[0]], fold)
    if only_at != {"count": 1000}:
        bad.append(f"an event at the snapshot position must not be re-folded: {only_at}")

    # declare_projection bundles the config and fold; optional aggregate filters appear only when set.
    declared = declare_projection("sub_summary", ["app.x"], fold, {"count": 0}, snapshot_interval=1000)
    if declared["projection_id"] != "sub_summary" or declared["fold"] is not fold or declared["snapshot_interval"] != 1000:
        bad.append(f"declare_projection should carry id/fold/interval: {declared}")
    if "aggregate_type" in declared or "aggregate_id" in declared:
        bad.append("declare_projection should omit unset aggregate filters")
    scoped = declare_projection("p", ["e"], fold, {}, aggregate_type="order", aggregate_id="o1")
    if scoped.get("aggregate_type") != "order" or scoped.get("aggregate_id") != "o1" or scoped["snapshot_interval"] is not None:
        bad.append(f"declare_projection should carry set filters and a None default interval: {scoped}")
    return bad


def _probe_otel():
    """The OTel export projection (section 7): the pure half of the exporter — map an hf.* event to its
    OTel signal kind (§7.1) and its semantic-convention attributes (§7.2, §7.3). Running the export loop
    against an injected SDK exporter is the boundary's, exactly as with the emit runtime."""
    from honest_observe import otel_attributes, otel_signal, otel_signal_kind

    bad = []

    # The §7.1 signal-kind map; an event that is not a framework signal maps to None.
    kinds = {
        "hf.chain.started": "span_start",
        "hf.chain.completed": "span_end",
        "hf.link.executed": "child_span",
        "hf.link.faulted": "span_event",
        "hf.persist.query": "child_span",
        "hf.classify.completed": "metric_counter",
        "hf.state.transitioned": "span_event",
    }
    for event_type, kind in kinds.items():
        if otel_signal_kind(event_type) != kind:
            bad.append(f"otel_signal_kind({event_type}) should be {kind}: {otel_signal_kind(event_type)}")
    if otel_signal_kind("app.order.placed") is not None:
        bad.append("a non-framework event has no OTel signal kind")

    # §7.3 hf.* attributes per event type, read from the payload.
    chain_done = {"event_type": "hf.chain.completed", "payload": {"chain_name": "checkout", "link_count": 3, "result": "err", "fault_code": "declined"}}
    if otel_attributes(chain_done) != {"hf.chain.name": "checkout", "hf.chain.link_count": 3, "hf.chain.fault_code": "declined"}:
        bad.append(f"chain.completed attributes wrong: {otel_attributes(chain_done)}")
    chain_ok = {"event_type": "hf.chain.completed", "payload": {"chain_name": "checkout", "link_count": 3, "result": "ok"}}
    if otel_attributes(chain_ok) != {"hf.chain.name": "checkout", "hf.chain.link_count": 3}:
        bad.append(f"a successful chain.completed should carry no fault code attribute: {otel_attributes(chain_ok)}")
    chain_started = {"event_type": "hf.chain.started", "payload": {"chain_name": "checkout", "link_count": 3, "input_types": []}}
    if otel_attributes(chain_started) != {"hf.chain.name": "checkout", "hf.chain.link_count": 3}:
        bad.append(f"chain.started attributes should omit a fault code: {otel_attributes(chain_started)}")
    link = {"event_type": "hf.link.executed", "payload": {"link_name": "validate", "chain_name": "checkout", "boundary": True, "mutations": 0, "singletons": 1, "nondeterminism": False, "io_calls": 2, "duration_ns": 9, "result": "ok"}}
    if otel_attributes(link) != {"hf.link.name": "validate", "hf.link.boundary": True, "hf.link.mutations": 0, "hf.link.singletons": 1, "hf.link.nondeterminism": False, "hf.link.io_calls": 2}:
        bad.append(f"link.executed attributes wrong: {otel_attributes(link)}")
    faulted = {"event_type": "hf.link.faulted", "payload": {"link_name": "pay", "chain_name": "checkout", "fault_code": "declined", "fault_category": "client", "fault_message": "no"}}
    if otel_attributes(faulted) != {"hf.link.name": "pay"}:
        bad.append(f"link.faulted attributes wrong: {otel_attributes(faulted)}")
    classify = {"event_type": "hf.classify.completed", "payload": {"vocabulary_name": "order_vocab", "token_count": 5, "rejection_count": 1, "duration_ns": 3, "rejection_reasons": {}}}
    if otel_attributes(classify) != {"hf.vocabulary.name": "order_vocab", "hf.classify.rejection_count": 1}:
        bad.append(f"classify attributes wrong: {otel_attributes(classify)}")
    state = {"event_type": "hf.state.transitioned", "payload": {"machine_name": "order_sm", "entity_id": "o1", "from_state": "pending", "event": "pay", "to_state": "paid", "duration_ns": 4}}
    if otel_attributes(state) != {"hf.state.machine": "order_sm", "hf.state.from": "pending", "hf.state.event": "pay", "hf.state.to": "paid"}:
        bad.append(f"state attributes wrong: {otel_attributes(state)}")

    # An event with no hf.* attribute builder (e.g. persist.query, mapped only by kind) yields no hf.* attrs.
    persist_q = {"event_type": "hf.persist.query", "payload": {"sql": "SELECT 1"}}
    if otel_attributes(persist_q) != {}:
        bad.append(f"an event with no attribute builder yields no attributes: {otel_attributes(persist_q)}")

    # §7.2 service.version is sourced from meta.release, and attaches across any event that carries it.
    with_release = {"event_type": "hf.chain.started", "payload": {"chain_name": "c", "link_count": 1, "input_types": []}, "meta": {"release": "1.4.0"}}
    if otel_attributes(with_release).get("service.version") != "1.4.0":
        bad.append("service.version should come from meta.release")
    if "service.version" in otel_attributes({"event_type": "hf.persist.query", "payload": {}, "meta": {"other": "x"}}):
        bad.append("service.version should be absent when meta has no release")

    # §7.3 hf.auth.* attributes come from the event's auth partition (when honest-auth is used): every
    # field present maps, only the fields present map, and a no-auth event carries none.
    with_auth = {"event_type": "hf.link.executed", "payload": link["payload"], "auth": {"caller_id": "u1", "data_owner_id": "o1", "factors_presented": ["pw"]}}
    got_auth = {k: v for k, v in otel_attributes(with_auth).items() if k.startswith("hf.auth")}
    if got_auth != {"hf.auth.caller_id": "u1", "hf.auth.data_owner_id": "o1", "hf.auth.factors_presented": ["pw"]}:
        bad.append(f"the auth partition should map to hf.auth.* attributes: {got_auth}")
    if {k for k in otel_attributes({**with_auth, "auth": {"caller_id": "u1"}}) if k.startswith("hf.auth")} != {"hf.auth.caller_id"}:
        bad.append("only the auth fields present in the partition should map")
    if any(k.startswith("hf.auth") for k in otel_attributes({**with_auth, "auth": None})):
        bad.append("a no-auth event should carry no hf.auth.* attributes")

    # otel_signal is the projection's output: kind plus attributes for one event.
    sig = otel_signal(chain_done)
    if sig != {"event_type": "hf.chain.completed", "kind": "span_end", "attributes": {"hf.chain.name": "checkout", "hf.chain.link_count": 3, "hf.chain.fault_code": "declined"}}:
        bad.append(f"otel_signal wrong: {sig}")
    return bad


def _probe_browser():
    """Browser instrumentation (section 8): the browser event envelope (§8.2) and the four automatic
    browser event payloads (§8.4), as pure data contracts. The beacon and the ingest endpoint that
    receives them are boundary I/O; the shapes here are what that endpoint validates and appends."""
    from honest_observe import browser_classify, browser_request, browser_response, build_browser_event, dom_changed

    bad = []

    # §8.2 envelope: source is always "browser"; request_id attaches only when supplied; required
    # fields are validated exactly as the server envelope is.
    ok_event = build_browser_event("hf.dom.changed", "1.0", "2026-03-15T14:23:07.001Z", "sess-1", {"changed_keys": ["filters"]}, "uuid-v4-1", request_id="req_abc")
    if "ok" not in ok_event:
        bad.append(f"a complete browser event should be ok: {ok_event}")
    else:
        env = ok_event["ok"]
        if env["source"] != "browser" or env["session_id"] != "sess-1" or env["request_id"] != "req_abc" or env["payload"] != {"changed_keys": ["filters"]}:
            bad.append(f"browser envelope wrong: {env}")
        if "aggregate_type" in env or "sequence" in env:
            bad.append("a browser event has no aggregate or sequence fields")
    no_req = build_browser_event("hf.dom.changed", "1.0", "2026-03-15T14:23:07.001Z", "sess-1", {}, "uuid-v4-2")
    if "request_id" in no_req["ok"]:
        bad.append("request_id must be absent when not supplied")
    bad_event = build_browser_event("hf.dom.changed", "1.0", "2026-03-15T14:23:07.001Z", "", {}, "uuid-v4-3")
    if bad_event != {"err": {"code": "invalid_event", "message": "Browser event is missing required field(s): ['session_id']", "category": "client", "detail": {"missing": ["session_id"]}}}:
        bad.append(f"an empty required field (session_id) should fault invalid_event in full: {bad_event}")

    # §8.4 the four automatic browser events.
    classify = browser_classify("#row-1", "hf-format", ["currency", "usd"], {"format": "currency"}, 1200, request_id="req_abc")
    if classify != {"event_type": "hf.browser.classify", "payload": {"element": "#row-1", "attribute": "hf-format", "tokens": ["currency", "usd"], "manifest": {"format": "currency"}, "duration_ns": 1200, "request_id": "req_abc"}}:
        bad.append(f"browser_classify wrong: {classify}")
    if "request_id" in browser_classify("#x", "hf-y", [], {}, 1)["payload"]:
        bad.append("browser_classify should omit request_id when not supplied")

    request = browser_request("POST", "/api/items", "change", "#content", ["filters", "page"], "req_abc")
    if request != {"event_type": "hf.browser.request", "payload": {"method": "POST", "url": "/api/items", "trigger": "change", "target": "#content", "manifest_keys": ["filters", "page"], "request_id": "req_abc"}}:
        bad.append(f"browser_request wrong: {request}")

    response = browser_response("req_abc", 200, "#content-area", 163)
    if response != {"event_type": "hf.browser.response", "payload": {"request_id": "req_abc", "status": 200, "swap_target": "#content-area", "duration_ms": 163}}:
        bad.append(f"browser_response wrong: {response}")

    changed = dom_changed(["filters"], {"filters": []}, {"filters": ["active"]}, request_id="req_abc")
    if changed != {"event_type": "hf.dom.changed", "payload": {"changed_keys": ["filters"], "from": {"filters": []}, "to": {"filters": ["active"]}, "request_id": "req_abc"}}:
        bad.append(f"dom_changed wrong: {changed}")
    if "request_id" in dom_changed(["x"], {"x": 1}, {"x": 2})["payload"]:
        bad.append("dom_changed should omit request_id outside a request context")
    return bad


def _probe_tail():
    """The tail line formatter (section 9.2): one event rendered as a structured time/source/type/fields
    line. A pure projection — the CLI that streams the log and prints is the boundary; this is the format
    it prints. Field rendering is dict-dispatched per event type, with an empty tail for an unmapped one."""
    from honest_observe import format_tail_line

    bad = []

    link = {"event_type": "hf.link.executed", "source": "server", "timestamp": "2026-03-15T14:23:07.006Z", "payload": {"link_name": "validate_filters", "chain_name": "fetch_items", "result": "ok", "duration_ns": 800000}}
    if format_tail_line(link) != "14:23:07.006 server  hf.link.executed  link=validate_filters chain=fetch_items result=ok duration=0.8ms":
        bad.append(f"link tail line wrong: {format_tail_line(link)!r}")

    # source defaults to "server" when absent (server events carry no source field); a browser event names its source.
    canonical = {"event_type": "hf.request.canonical", "timestamp": "2026-03-15T14:23:07.023Z", "payload": {"http_method": "POST", "http_path": "/api/items", "http_status": 200, "duration_ns": 16000000}}
    if format_tail_line(canonical) != "14:23:07.023 server  hf.request.canonical  method=POST path=/api/items status=200 duration=16.0ms":
        bad.append(f"canonical tail line wrong: {format_tail_line(canonical)!r}")
    resp = {"event_type": "hf.browser.response", "source": "browser", "timestamp": "2026-03-15T14:23:07.166Z", "payload": {"request_id": "req_abc", "status": 200, "swap_target": "#x", "duration_ms": 163}}
    if format_tail_line(resp) != "14:23:07.166 browser hf.browser.response  status=200 duration=163ms req=req_abc":
        bad.append(f"browser response tail line wrong: {format_tail_line(resp)!r}")

    # Every mapped event type renders a non-empty field tail; cover each renderer.
    cases = [
        ({"event_type": "hf.chain.started", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"chain_name": "c", "link_count": 3}}, "chain=c links=3"),
        ({"event_type": "hf.chain.completed", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"chain_name": "c", "result": "ok", "duration_ns": 16000000}}, "chain=c result=ok duration=16.0ms"),
        ({"event_type": "hf.classify.completed", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"token_count": 3, "rejection_count": 0}}, "tokens=3 rejected=0"),
        ({"event_type": "hf.state.transitioned", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"machine_name": "sm", "from_state": "a", "to_state": "b"}}, "machine=sm a->b"),
        ({"event_type": "hf.browser.request", "source": "browser", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"method": "POST", "url": "/x"}}, "method=POST url=/x"),
        ({"event_type": "hf.dom.changed", "source": "browser", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"changed_keys": ["filters"]}}, "keys=['filters']"),
        ({"event_type": "hf.browser.classify", "source": "browser", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"element": "#r", "attribute": "hf-format"}}, "element=#r attribute=hf-format"),
    ]
    for event, tail in cases:
        if not format_tail_line(event).endswith(tail):
            bad.append(f"{event['event_type']} tail line should end with {tail!r}: {format_tail_line(event)!r}")

    # An unmapped event type still renders time/source/type, with an empty field tail.
    unmapped = {"event_type": "app.custom", "timestamp": "2026-01-01T00:00:00.000Z", "payload": {"x": 1}}
    if format_tail_line(unmapped) != "00:00:00.000 server  app.custom  ":
        bad.append(f"an unmapped event should render an empty field tail: {format_tail_line(unmapped)!r}")
    return bad


def _probe_inspect():
    """The inspect trace (section 9.3): one request reconstructed from its request_id — server trace
    from the canonical event's denormalized link_sequence, browser trace from the browser events that
    carry the request_id, ordered BROWSER -> SERVER -> BROWSER, with a single-clock timing breakdown."""
    from honest_observe import format_inspect
    from honest_observe.devtools import _request_id_of

    bad = []

    # _request_id_of finds the id wherever present, and only where present.
    if _request_id_of({"request_id": "r1", "payload": {}}) != "r1":
        bad.append("_request_id_of should read the envelope request_id")
    if _request_id_of({"payload": {"request_id": "r2"}}) != "r2":
        bad.append("_request_id_of should fall back to the payload request_id")
    if _request_id_of({"aggregate_type": "request", "aggregate_id": "r3", "payload": {}}) != "r3":
        bad.append("_request_id_of should use the aggregate_id of a request event")
    if _request_id_of({"aggregate_type": "link", "aggregate_id": "validate", "payload": {}}) is not None:
        bad.append("_request_id_of should be None when no request_id is present")

    canonical = {
        "event_type": "hf.request.canonical", "aggregate_type": "request", "aggregate_id": "req_abc",
        "timestamp": "2026-03-15T14:23:07.023Z",
        "payload": {
            "request_id": "req_abc", "http_method": "POST", "http_path": "/api/items", "http_status": 200,
            "duration_ns": 16000000, "source": "server",
            "link_sequence": [
                {"link_name": "validate_filters", "duration_ns": 800000, "result": "ok"},
                {"link_name": "build_query", "duration_ns": 400000, "result": "ok"},
                {"link_name": "pay", "duration_ns": 300000, "result": "err", "fault_code": "declined"},
            ],
        },
    }
    dom_before = {"event_type": "hf.dom.changed", "source": "browser", "request_id": "req_abc", "timestamp": "2026-03-15T14:23:07.001Z", "payload": {"changed_keys": ["filters"]}}
    req = {"event_type": "hf.browser.request", "source": "browser", "request_id": "req_abc", "timestamp": "2026-03-15T14:23:07.003Z", "payload": {"method": "POST", "url": "/api/items"}}
    resp = {"event_type": "hf.browser.response", "source": "browser", "request_id": "req_abc", "timestamp": "2026-03-15T14:23:07.166Z", "payload": {"status": 200, "swap_target": "#content-area", "duration_ms": 163, "request_id": "req_abc"}}
    classify = {"event_type": "hf.browser.classify", "source": "browser", "request_id": "req_abc", "timestamp": "2026-03-15T14:23:07.171Z", "payload": {"element": "#content-area", "attribute": "hf-format", "duration_ns": 3000000}}
    foreign = {"event_type": "hf.dom.changed", "source": "browser", "request_id": "other", "timestamp": "2026-03-15T14:23:07.500Z", "payload": {"changed_keys": ["x"]}}
    # A non-request event that merely shares the aggregate_id must NOT be picked as the canonical: the
    # lookup needs aggregate_type == "request" AND aggregate_id == request_id (pins the `and`).
    decoy = {"event_type": "hf.link.executed", "aggregate_type": "link", "aggregate_id": "req_abc", "timestamp": "2026-03-15T14:23:07.000Z", "payload": {"link_name": "x"}}

    # The full trace is pinned exactly: every separator, the BROWSER -> SERVER -> BROWSER ordering,
    # each browser detail line, the server link_sequence with the fault on the errored link, the
    # foreign-request exclusion, the aggregate-id decoy exclusion, and the timing footer.
    trace = format_inspect("req_abc", [decoy, dom_before, req, canonical, resp, classify, foreign])
    expected_trace = (
        "Request: req_abc\n"
        "POST /api/items → 200  total: 166ms\n\n"
        "BROWSER\n"
        "  14:23:07.001  dom.changed  ['filters']\n"
        "  14:23:07.003  browser.request  POST /api/items\n\n"
        "SERVER\n"
        "  link  validate_filters  ok  0.8ms\n"
        "  link  build_query  ok  0.4ms\n"
        "  link  pay  err  0.3ms  declined\n\n"
        "BROWSER\n"
        "  14:23:07.166  browser.response  200  #content-area  163ms\n"
        "  14:23:07.171  browser.classify  #content-area  hf-format\n\n"
        "Total: 166ms  (server: 16ms  network: 147ms  browser: 3ms)"
    )
    if trace != expected_trace:
        bad.append(f"inspect trace wrong:\n{trace!r}\nexpected:\n{expected_trace!r}")

    # A request with no browser side: server block alone, network and browser zero.
    server_only = format_inspect("req_abc", [canonical])
    if "BROWSER" in server_only or not server_only.endswith("Total: 16ms  (server: 16ms  network: 0ms  browser: 0ms)"):
        bad.append(f"a server-only request should render the server block alone: {server_only}")

    # A browser event at exactly the canonical timestamp belongs to the after section (>=) and appears
    # exactly once — pinning the < / >= boundary of the before/after split.
    at_canonical = {"event_type": "hf.dom.changed", "source": "browser", "request_id": "req_abc", "timestamp": "2026-03-15T14:23:07.023Z", "payload": {"changed_keys": ["edge"]}}
    edge = format_inspect("req_abc", [canonical, at_canonical])
    if edge.count("dom.changed  ['edge']") != 1 or edge.count("BROWSER") != 1:
        bad.append(f"an event at the canonical timestamp should appear once, in the after section: {edge}")
    return bad


def _probe_query():
    """The named-projection runner (section 9.4): resolve a projection by name from a registry and run
    it over the events. An unknown name is a fault as data; a known one folds and returns ok(state)."""
    from honest_observe import declare_projection, run_named_projection

    bad = []

    def count(state, event):
        return {"n": state["n"] + 1}

    registry = {"clicks": declare_projection("clicks", ["click"], count, {"n": 0})}
    events = [
        {"event_type": "click", "timestamp": "2026-01-01T00:00:00Z", "payload": {}},
        {"event_type": "view", "timestamp": "2026-01-01T00:00:01Z", "payload": {}},
        {"event_type": "click", "timestamp": "2026-01-01T00:00:02Z", "payload": {}},
    ]
    result = run_named_projection(registry, "clicks", events)
    if result != {"ok": {"n": 2}}:
        bad.append(f"a known projection should run its fold over the filtered events: {result}")

    # A projection declaring an aggregate_id filter folds only that id; one declaring an aggregate_type
    # filter folds only that type — so both the aggregate_type and aggregate_id the runner threads
    # through are independently pinned.
    by_id = {"p": declare_projection("p", None, lambda state, event: state + 1, 0, aggregate_id="o1")}
    by_type = {"p": declare_projection("p", None, lambda state, event: state + 1, 0, aggregate_type="order")}
    mixed_events = [
        {"event_type": "x", "aggregate_type": "order", "aggregate_id": "o1", "timestamp": "t", "payload": {}},
        {"event_type": "x", "aggregate_type": "refund", "aggregate_id": "o1", "timestamp": "t", "payload": {}},
        {"event_type": "x", "aggregate_type": "order", "aggregate_id": "o2", "timestamp": "t", "payload": {}},
    ]
    if run_named_projection(by_id, "p", mixed_events) != {"ok": 2}:
        bad.append(f"an aggregate_id filter should fold only that id: {run_named_projection(by_id, 'p', mixed_events)}")
    if run_named_projection(by_type, "p", mixed_events) != {"ok": 2}:
        bad.append(f"an aggregate_type filter should fold only that type: {run_named_projection(by_type, 'p', mixed_events)}")

    # An unknown name is a full fault as data — code, message, category, and detail all pinned.
    missing = run_named_projection(registry, "nope", events)
    if missing != {"err": {"code": "unknown_projection", "message": "No projection named 'nope' in the registry", "category": "client", "detail": {"name": "nope"}}}:
        bad.append(f"an unknown projection name should be a complete fault as data: {missing}")
    return bad


def _probe_threshold_engine():
    """The threshold metric engine (section 8b): a metric is a fold plus a value over the log
    (custom_metric / compute_metric), and a condition is the threshold-crossing decision
    (condition_met). All pure; sending the alert, storing the rule, and the cooldown are other modules."""
    from honest_observe import compute_metric, condition_met, custom_metric

    bad = []

    # condition_met is the threshold comparator (section 8b.4 ConditionSpec operator/value).
    checks = [
        ("gt over", condition_met(0.06, {"operator": "gt", "value": 0.05}), True),
        ("gt under", condition_met(0.04, {"operator": "gt", "value": 0.05}), False),
        ("gt equal", condition_met(5, {"operator": "gt", "value": 5}), False),     # strict: not >=
        ("lt under", condition_met(3, {"operator": "lt", "value": 5}), True),
        ("lt over", condition_met(7, {"operator": "lt", "value": 5}), False),
        ("lt equal", condition_met(5, {"operator": "lt", "value": 5}), False),     # strict: not <=
        ("gte equal", condition_met(5, {"operator": "gte", "value": 5}), True),
        ("gte under", condition_met(4, {"operator": "gte", "value": 5}), False),
        ("lte equal", condition_met(5, {"operator": "lte", "value": 5}), True),
        ("lte over", condition_met(6, {"operator": "lte", "value": 5}), False),
    ]
    for label, got, want in checks:
        if got != want:
            bad.append(f"condition_met({label}) should be {want}, got {got}")

    # A metric is a fold accumulating state plus a value extracting the number (the section 8b.5 pattern).
    def fold(state, event):
        return {"total": state["total"] + 1, "failed": state["failed"] + (1 if event["payload"]["result"] == "failure" else 0)}

    def value(state):
        return state["failed"] / state["total"] if state["total"] else 0.0

    metric = custom_metric("payment.failure_rate", ["app.payment.api_called"], fold, value, {"total": 0, "failed": 0})
    if metric["name"] != "payment.failure_rate" or metric["fold"] is not fold or metric["value"] is not value:
        bad.append(f"custom_metric should carry the name, fold, and value: {metric}")

    events = [
        {"event_type": "app.payment.api_called", "timestamp": "2026-01-01T00:00:00Z", "payload": {"result": "success"}},
        {"event_type": "app.payment.api_called", "timestamp": "2026-01-01T00:00:01Z", "payload": {"result": "failure"}},
        {"event_type": "app.payment.api_called", "timestamp": "2026-01-01T00:00:02Z", "payload": {"result": "success"}},
        {"event_type": "app.other", "timestamp": "2026-01-01T00:00:03Z", "payload": {}},
    ]
    # compute_metric folds only the metric's event types, then extracts the value: one failure in three.
    if compute_metric(metric, events) != 1 / 3:
        bad.append(f"compute_metric should fold the metric's events and extract the value: {compute_metric(metric, events)}")
    # Empty log: the value function's empty-state path (no division by zero).
    if compute_metric(metric, []) != 0.0:
        bad.append("compute_metric over an empty log should return the metric's empty value")
    return bad


def _probe_builtin_metrics():
    """The built-in threshold metrics (section 8b.3): ready-made metrics over the framework's own events,
    each a fold and a value the engine runs. Covers the self-contained metrics over observe-owned events,
    including the per-link metrics grouped by link; the persist-sourced metrics are deferred (see
    thresholds.py)."""
    from honest_observe import builtin_metrics, compute_metric
    from honest_observe.thresholds import _percentile

    bad = []

    # Percentile by nearest rank: empty is zero, a single value is itself, p99 of 1..100 is 99.
    if _percentile([], 99) != 0:
        bad.append("the percentile of no values should be zero")
    if _percentile([42], 99) != 42:
        bad.append("the percentile of one value should be that value")
    if _percentile(list(range(1, 101)), 99) != 99:
        bad.append(f"p99 of 1..100 should be 99: {_percentile(list(range(1, 101)), 99)}")
    if _percentile(list(range(1, 101)), 98) != 98 or _percentile(list(range(1, 101)), 100) != 100:
        bad.append("p98 of 1..100 should be 98 and p100 should be 100 (pins the percentile arithmetic)")
    if _percentile(list(range(1, 102)), 100) != 101:
        bad.append(f"p100 of 1..101 should be 101 (pins the p/100 rank divisor): {_percentile(list(range(1, 102)), 100)}")

    metrics = builtin_metrics()
    # Every built-in metric's internal name matches its registry key (pins the name argument).
    for key, metric_decl in metrics.items():
        if metric_decl["name"] != key:
            bad.append(f"built-in metric {key!r} should carry its own name: {metric_decl['name']!r}")
    canonical = [
        {"event_type": "hf.request.canonical", "timestamp": "2026-01-01T00:00:00Z", "payload": {"result": "ok", "duration_ns": 100}},
        {"event_type": "hf.request.canonical", "timestamp": "2026-01-01T00:00:01Z", "payload": {"result": "err", "duration_ns": 300}},
    ]
    if compute_metric(metrics["request.error_rate"], canonical) != 0.5:
        bad.append(f"request.error_rate should be the err fraction: {compute_metric(metrics['request.error_rate'], canonical)}")
    if compute_metric(metrics["request.rate_per_minute"], canonical) != 2:
        bad.append("request.rate_per_minute should count the requests")
    if compute_metric(metrics["request.p99_duration_ns"], canonical) != 300:
        bad.append("request.p99_duration_ns should be the 99th-percentile duration")
    # Over 100 distinct durations the metric's hardcoded 99th percentile is pinned (a 2-sample input
    # cannot distinguish p98/p99/p100).
    hundred = [{"event_type": "hf.request.canonical", "timestamp": "t", "payload": {"result": "ok", "duration_ns": n}} for n in range(1, 101)]
    if compute_metric(metrics["request.p99_duration_ns"], hundred) != 99:
        bad.append(f"request.p99_duration_ns over 1..100 should be 99: {compute_metric(metrics['request.p99_duration_ns'], hundred)}")
    hundred_ms = [{"event_type": "hf.browser.response", "timestamp": "t", "payload": {"duration_ms": n}} for n in range(1, 101)]
    if compute_metric(metrics["browser.response.p99_duration_ms"], hundred_ms) != 99:
        bad.append(f"browser.response.p99_duration_ms over 1..100 should be 99: {compute_metric(metrics['browser.response.p99_duration_ms'], hundred_ms)}")
    # The empty-log path of the rate value (the no-division branch).
    if compute_metric(metrics["request.error_rate"], []) != 0.0:
        bad.append("request.error_rate over an empty log should be zero")

    classify = [
        {"event_type": "hf.classify.completed", "timestamp": "2026-01-01T00:00:00Z", "payload": {"token_count": 7, "rejection_count": 1}},
        {"event_type": "hf.classify.completed", "timestamp": "2026-01-01T00:00:01Z", "payload": {"token_count": 3, "rejection_count": 1}},
    ]
    if compute_metric(metrics["classify.rejection_rate"], classify) != 0.2:
        bad.append(f"classify.rejection_rate should be rejected over tokens: {compute_metric(metrics['classify.rejection_rate'], classify)}")
    if compute_metric(metrics["classify.rejection_rate"], []) != 0.0:
        bad.append("classify.rejection_rate over an empty log should be zero")

    links = [
        {"event_type": "hf.link.executed", "timestamp": "2026-01-01T00:00:00Z", "payload": {"mutations": 1, "nondeterminism": True}},
        {"event_type": "hf.link.executed", "timestamp": "2026-01-01T00:00:01Z", "payload": {"mutations": 2, "nondeterminism": False}},
        {"event_type": "hf.link.executed", "timestamp": "2026-01-01T00:00:02Z", "payload": {"mutations": 0, "nondeterminism": True}},
    ]
    if compute_metric(metrics["honesty.mutation_count"], links) != 3:
        bad.append("honesty.mutation_count should sum the mutations")
    # Two nondeterministic, one deterministic — distinguishes counting the True case from the False case.
    if compute_metric(metrics["honesty.nondeterminism_count"], links) != 2:
        bad.append(f"honesty.nondeterminism_count should count the nondeterministic links: {compute_metric(metrics['honesty.nondeterminism_count'], links)}")

    responses = [
        {"event_type": "hf.browser.response", "timestamp": "2026-01-01T00:00:00Z", "payload": {"duration_ms": 100}},
        {"event_type": "hf.browser.response", "timestamp": "2026-01-01T00:00:01Z", "payload": {"duration_ms": 200}},
    ]
    if compute_metric(metrics["browser.response.p99_duration_ms"], responses) != 200:
        bad.append("browser.response.p99_duration_ms should be the 99th-percentile round trip")

    # The per-link metrics are grouped by link_name: one value per link (section 8b.3), and an empty log
    # is an empty mapping.
    link_exec = [
        {"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "validate", "result": "ok", "duration_ns": 10}},
        {"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "charge", "result": "err", "duration_ns": 50}},
        {"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "charge", "result": "ok", "duration_ns": 40}},
    ]
    if compute_metric(metrics["link.fault_rate"], link_exec) != {"validate": 0.0, "charge": 0.5}:
        bad.append(f"link.fault_rate should be the fault fraction per link: {compute_metric(metrics['link.fault_rate'], link_exec)}")
    if compute_metric(metrics["link.p99_duration_ns"], link_exec) != {"validate": 10, "charge": 50}:
        bad.append(f"link.p99_duration_ns should be the 99th-percentile duration per link: {compute_metric(metrics['link.p99_duration_ns'], link_exec)}")
    # One link with 100 distinct durations pins its 99th percentile at 99 (a 2-sample group cannot).
    hundred_link = [{"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "slow", "result": "ok", "duration_ns": n}} for n in range(1, 101)]
    if compute_metric(metrics["link.p99_duration_ns"], hundred_link) != {"slow": 99}:
        bad.append(f"link.p99_duration_ns over 1..100 for one link should be 99: {compute_metric(metrics['link.p99_duration_ns'], hundred_link)}")
    if compute_metric(metrics["link.fault_rate"], []) != {}:
        bad.append("a grouped metric over an empty log should be an empty mapping")
    return bad


def _probe_threshold_projection():
    """The threshold projection (section 8b.2) and its firing decision: declare what to watch and the
    line to cross (threshold_projection), then decide whether it fires now (evaluate_threshold). Pure;
    the cooldown timing, the alert send, and the remediation chain are the boundary's."""
    from honest_observe import builtin_metrics, evaluate_threshold, threshold_projection

    bad = []

    alert = {"message_type": "hf.alert.high_error_rate", "recipient": {"type": "role", "id": "on_call"}, "dom_surface": "banner"}
    declared = threshold_projection("high_error_rate", "request.error_rate", {"operator": "gt", "value": 0.05}, "5m", "10m", alert, remediation="investigate", enabled=True)
    if declared != {
        "projection_id": "high_error_rate", "metric": "request.error_rate", "condition": {"operator": "gt", "value": 0.05},
        "window": "5m", "cooldown": "10m", "alert": alert, "enabled": True, "remediation": "investigate",
    }:
        bad.append(f"threshold_projection full shape wrong: {declared}")
    if "remediation" in threshold_projection("p", "m", {"operator": "gt", "value": 1}, "1m", "1m", alert):
        bad.append("threshold_projection should omit remediation when not supplied")
    # enabled defaults to True, so a projection declared without it still evaluates and can fire.
    if threshold_projection("p", "m", {"operator": "gt", "value": 1}, "1m", "1m", alert)["enabled"] is not True:
        bad.append("threshold_projection enabled should default to True")

    metric = builtin_metrics()["request.error_rate"]
    over = [
        {"event_type": "hf.request.canonical", "timestamp": "2026-01-01T00:00:00Z", "payload": {"result": "err", "duration_ns": 1}},
        {"event_type": "hf.request.canonical", "timestamp": "2026-01-01T00:00:01Z", "payload": {"result": "ok", "duration_ns": 1}},
    ]
    fired = evaluate_threshold(declared, metric, over)
    if fired != {"fired": True, "value": 0.5}:
        bad.append(f"an enabled threshold over its line should fire with the value: {fired}")

    under = [{"event_type": "hf.request.canonical", "timestamp": "2026-01-01T00:00:00Z", "payload": {"result": "ok", "duration_ns": 1}}]
    if evaluate_threshold(declared, metric, under) != {"fired": False, "value": 0.0}:
        bad.append("an enabled threshold under its line should not fire")

    disabled = threshold_projection("off", "request.error_rate", {"operator": "gt", "value": 0.05}, "5m", "10m", alert, enabled=False)
    if evaluate_threshold(disabled, metric, over) != {"fired": False, "value": None}:
        bad.append("a disabled threshold never fires and reports no value")

    # A threshold declared on a grouped (per-link) metric fires per link: one {group, fired, value} per
    # link, and `fired` is true when any link crosses the line (section 8b, per-link firing).
    per_link = threshold_projection("link_faults", "link.fault_rate", {"operator": "gt", "value": 0.25}, "5m", "10m", alert)
    link_metric = builtin_metrics()["link.fault_rate"]
    link_events = [
        {"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "ok_link", "result": "ok", "duration_ns": 1}},
        {"event_type": "hf.link.executed", "timestamp": "t", "payload": {"link_name": "bad_link", "result": "err", "duration_ns": 1}},
    ]
    if evaluate_threshold(per_link, link_metric, link_events) != {"fired": True, "firings": [{"group": "ok_link", "fired": False, "value": 0.0}, {"group": "bad_link", "fired": True, "value": 1.0}]}:
        bad.append(f"a per-link threshold should fire per link over the line: {evaluate_threshold(per_link, link_metric, link_events)}")
    calm = evaluate_threshold(per_link, link_metric, link_events[:1])
    if calm["fired"] or calm["firings"] != [{"group": "ok_link", "fired": False, "value": 0.0}]:
        bad.append(f"a per-link threshold with no link over the line should not fire: {calm}")
    return bad


def _probe_rejection():
    """External-ingest rejections (section 8c.5): a raw event that fails translation or identity
    resolution becomes a rejection record — data, not an exception — and the honest_rejection_log is the
    append-only table it lands in (section 8c.7), observe's to define as data, persist's to apply."""
    from honest_observe import rejection, rejection_log_manifest, rejection_log_schema

    bad = []

    record = rejection("stripe", "unrecognized_shape", {"missing": "amount"}, {"id": "evt_1"}, "1.0", "rej-uuid-1", "2026-03-15T14:23:07Z")
    if record != {
        "rejection_id": "rej-uuid-1", "received_at": "2026-03-15T14:23:07Z", "source": "stripe",
        "reason_code": "unrecognized_shape", "reason_detail": {"missing": "amount"},
        "raw_event": {"id": "evt_1"}, "translator_version": "1.0",
    }:
        bad.append(f"rejection record wrong: {record}")

    # The full schema dict is pinned exactly: every column definition (type, nullable, primary_key),
    # the primary key, and all three forensic indexes with their columns.
    expected_table = {
        "columns": {
            "rejection_id": {"type": "text", "primary_key": True, "nullable": False},
            "received_at": {"type": "text", "nullable": False},
            "source": {"type": "text", "nullable": False},
            "reason_code": {"type": "text", "nullable": False},
            "reason_detail": {"type": "text", "nullable": False},
            "raw_event": {"type": "text", "nullable": False},
            "translator_version": {"type": "text", "nullable": False},
        },
        "primary_key": ["rejection_id"],
        "indexes": {"idx_source": {"columns": ["source"]}, "idx_reason": {"columns": ["reason_code"]}, "idx_received": {"columns": ["received_at"]}},
    }
    schema = rejection_log_schema()
    if schema != {"honest_rejection_log": expected_table}:
        bad.append(f"rejection_log_schema wrong: {schema}")
    if rejection_log_manifest() != {"table": "honest_rejection_log", "append_only": True, "schema": expected_table}:
        bad.append(f"rejection_log_manifest wrong: {rejection_log_manifest()}")
    return bad


def _probe_hlc():
    """Hybrid Logical Clocks (section 8c.2): a causal total order across sources that do not share a
    clock. Pure — the physical clock is read at the boundary and passed in. hlc_send advances on a local
    event, hlc_receive merges an incoming clock, hlc_compare gives the total order."""
    from honest_observe import hlc_compare, hlc_receive, hlc_send

    bad = []

    # Send: when the wall clock has advanced, take it and reset the logical counter; when it has not,
    # keep the physical time and increment the logical counter (so same-millisecond events still order).
    if hlc_send({"physical": 10, "logical": 5, "source": "a"}, 20) != {"physical": 20, "logical": 0, "source": "a"}:
        bad.append("hlc_send should take an advanced wall clock and reset logical")
    if hlc_send({"physical": 10, "logical": 5, "source": "a"}, 8) != {"physical": 10, "logical": 6, "source": "a"}:
        bad.append("hlc_send should keep physical and increment logical when the clock did not advance")

    # Receive: new physical is the max of local, incoming, and the wall clock; the logical counter is
    # chosen by which of those the max came from (canonical HLC receive).
    if hlc_receive({"physical": 10, "logical": 2, "source": "a"}, {"physical": 10, "logical": 3, "source": "b"}, 5) != {"physical": 10, "logical": 4, "source": "a"}:
        bad.append("hlc_receive with local==incoming should take max logical + 1")
    if hlc_receive({"physical": 10, "logical": 2, "source": "a"}, {"physical": 8, "logical": 9, "source": "b"}, 7) != {"physical": 10, "logical": 3, "source": "a"}:
        bad.append("hlc_receive when local physical wins should increment the local logical")
    if hlc_receive({"physical": 8, "logical": 2, "source": "a"}, {"physical": 10, "logical": 9, "source": "b"}, 7) != {"physical": 10, "logical": 10, "source": "a"}:
        bad.append("hlc_receive when incoming physical wins should increment the incoming logical")
    if hlc_receive({"physical": 8, "logical": 2, "source": "a"}, {"physical": 9, "logical": 9, "source": "b"}, 20) != {"physical": 20, "logical": 0, "source": "a"}:
        bad.append("hlc_receive when the wall clock wins should reset logical")

    # Compare: by physical, then logical, then source id; the receiver keeps its own source.
    order = [
        ({"physical": 10, "logical": 0, "source": "a"}, {"physical": 20, "logical": 0, "source": "a"}, -1),
        ({"physical": 20, "logical": 0, "source": "a"}, {"physical": 10, "logical": 0, "source": "a"}, 1),
        ({"physical": 10, "logical": 1, "source": "a"}, {"physical": 10, "logical": 2, "source": "a"}, -1),
        ({"physical": 10, "logical": 2, "source": "a"}, {"physical": 10, "logical": 2, "source": "b"}, -1),
        ({"physical": 10, "logical": 2, "source": "a"}, {"physical": 10, "logical": 2, "source": "a"}, 0),
    ]
    for a, b, want in order:
        if hlc_compare(a, b) != want:
            bad.append(f"hlc_compare({a}, {b}) should be {want}, got {hlc_compare(a, b)}")
    return bad


def _probe_identity():
    """Identity binding (section 8c.3): the same entity has different ids in different systems. Claims
    are events; bindings are a projection of claims; resolution is a lookup. All pure. A conflicting
    claim is data for adjudication, not a silent overwrite; an unresolvable id becomes an event."""
    from honest_observe import fold_identity_claims, identity_claimed, identity_unknown, resolve_identity

    bad = []

    claim = identity_claimed("user-42", "stripe", "cus_Nx3a9c", "webhook_signature_verified", "system:stripe_translator")
    if claim != {"event_type": "identity.claimed", "payload": {"canonical_id": "user-42", "external_system": "stripe", "external_id": "cus_Nx3a9c", "evidence": "webhook_signature_verified", "asserted_by": "system:stripe_translator"}}:
        bad.append(f"identity_claimed wrong: {claim}")

    if identity_unknown("cus_unknown", "stripe") != {"event_type": "identity.unknown", "payload": {"external_id": "cus_unknown", "source": "stripe"}}:
        bad.append(f"identity_unknown wrong: {identity_unknown('cus_unknown', 'stripe')}")

    # The binding projection folds claims into a lookup keyed by system then external id. A repeated
    # claim to the same canonical id is harmless; a claim to a different one is a conflict for adjudication.
    events = [
        identity_claimed("user-42", "stripe", "cus_Nx3a9c", "sig", "translator"),
        identity_claimed("user-7", "salesforce", "U000123", "api", "translator"),
        identity_claimed("user-42", "stripe", "cus_Nx3a9c", "sig", "translator"),
        identity_claimed("user-99", "stripe", "cus_Nx3a9c", "sig", "other"),
        {"event_type": "other.event", "payload": {}},
    ]
    folded = fold_identity_claims(events)
    if folded["bindings"] != {"stripe": {"cus_Nx3a9c": "user-42"}, "salesforce": {"U000123": "user-7"}}:
        bad.append(f"fold_identity_claims bindings wrong: {folded['bindings']}")
    if folded["conflicts"] != [{"external_system": "stripe", "external_id": "cus_Nx3a9c", "existing": "user-42", "claimed": "user-99"}]:
        bad.append(f"a conflicting claim should be recorded for adjudication, not overwrite: {folded['conflicts']}")

    # Resolution is a lookup against the bindings; an unknown external id resolves to None.
    bindings = folded["bindings"]
    if resolve_identity("cus_Nx3a9c", "stripe", bindings) != "user-42":
        bad.append("resolve_identity should map a known external id to its canonical id")
    if resolve_identity("cus_missing", "stripe", bindings) is not None:
        bad.append("resolve_identity should be None for an unknown external id")
    if resolve_identity("anything", "unknown_source", bindings) is not None:
        bad.append("resolve_identity should be None for an unknown source")
    return bad


def run():
    probes = {
        "build_event": _probe_build_event(),
        "extract": _probe_extract(),
        "matches": _probe_matches(),
        "projection": _probe_projection(),
        "emit": _probe_emit(),
        "framework_events": _probe_framework_events(),
        "canonical_app_events": _probe_canonical_app_events(),
        "event_log": _probe_event_log(),
        "snapshot": _probe_snapshot(),
        "otel": _probe_otel(),
        "browser": _probe_browser(),
        "tail": _probe_tail(),
        "inspect": _probe_inspect(),
        "query": _probe_query(),
        "threshold_engine": _probe_threshold_engine(),
        "builtin_metrics": _probe_builtin_metrics(),
        "threshold_projection": _probe_threshold_projection(),
        "rejection": _probe_rejection(),
        "hlc": _probe_hlc(),
        "identity": _probe_identity(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HO-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HO laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
