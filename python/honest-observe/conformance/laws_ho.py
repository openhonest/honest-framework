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

    # empty required field (event_type) -> invalid_event naming it.
    result = build_event(**{**_BASE, "event_type": ""})
    if result.get("err", {}).get("code") != "invalid_event" or "event_type" not in result["err"]["detail"]["missing"]:
        bad.append(f"an empty required field should fault invalid_event: {result}")

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
        if failed.get("err", {}).get("code") != "emit_failed" or failed["err"]["detail"]["cause"]["code"] != "log_write_failed":
            bad.append(f"an append failure should become emit_failed wrapping the cause: {failed}")
        return bad

    return asyncio.run(_run())


def run():
    probes = {
        "build_event": _probe_build_event(),
        "extract": _probe_extract(),
        "matches": _probe_matches(),
        "projection": _probe_projection(),
        "emit": _probe_emit(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HO-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HO laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
