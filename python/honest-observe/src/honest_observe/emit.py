"""emit (section 3): the one I/O boundary that writes an event to the log.

emit assembles a validated envelope (the pure build_event of section 2) and appends it. Everything
it cannot compute purely — the event_id, the timestamp, the per-aggregate sequence, the event-type
version, the auth/meta field names, and the log writer itself — is reached through one injected
`runtime`, never a global, a clock, or an import. Injecting `append` is what keeps honest-observe a
leaf above persist: observe is *stored by* persist but never *imports* it, so the dependency runs
one way and there is no cycle.

emit is async because the append is I/O. It does not catch — append returns a Result and emit
threads it; a malformed envelope returns its own validation fault, and nothing is written.
"""

from honest_type import err, fault, ok

from honest_observe.events import build_event, extract_auth, extract_meta


async def emit(event_type, aggregate_type, aggregate_id, payload, context, runtime):
    """Write one event to the log (section 3). Returns ok({event_id}), the envelope's validation
    fault if a required field is empty (nothing is written), or err(emit_failed) if the append
    fails. I/O — through the injected runtime only."""
    built = build_event(
        event_type,
        runtime.version(event_type),
        aggregate_type,
        aggregate_id,
        payload,
        runtime.event_id(),
        runtime.timestamp(),
        runtime.sequence(aggregate_id),
        auth=extract_auth(context, runtime.auth_fields),
        meta=extract_meta(context, runtime.meta_fields),
    )
    if "err" in built:
        return built
    event = built["ok"]
    written = await runtime.append(event)
    if "err" in written:
        return err(fault("emit_failed", "Failed to append event to the log", "server", {"cause": written["err"]}))
    return ok({"event_id": event["event_id"]})
