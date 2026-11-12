"""emit (section 3): write one event to the log.

emit is the door the world calls. It hands its input to run_emit with honest-observe's own
boundaries (new_event_id, event_timestamp, next_sequence and append_event, from boundaries).
run_emit assembles the validated envelope, the pure build_event of section 2, and appends it. A
test drives run_emit with a stand-in for each boundary and never touches the log. emit is async
because the append is I/O. Neither catches: append returns a Result and run_emit threads it, and a
malformed envelope returns its own validation fault with nothing written.
"""

from honest_type import err, fault, ok

from honest_observe.boundaries import append_event, event_timestamp, new_event_id, next_sequence
from honest_observe.events import build_event, extract_auth, extract_meta


async def run_emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn, new_event_id, event_timestamp, next_sequence, append_event, auth_fields, meta_fields):
    """Assemble the envelope with the handed-in boundaries and append it (section 3). Returns
    ok({event_id}), the envelope's validation fault if a required field is empty with nothing
    written, or err(emit_failed) if the append fails."""
    built = build_event(
        event_type,
        event_version,
        aggregate_type,
        aggregate_id,
        payload,
        new_event_id(),
        event_timestamp(),
        await next_sequence(aggregate_id, conn),
        auth=extract_auth(context, auth_fields),
        meta=extract_meta(context, meta_fields),
    )
    if "err" in built:
        return built
    event = built["ok"]
    written = await append_event(event, conn)
    if "err" in written:
        return err(fault("emit_failed", "Failed to append event to the log", "server", [], {"cause": written["err"]}))
    return ok({"event_id": event["event_id"]})


async def emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn, auth_fields, meta_fields):
    """The door: the world calls emit; it hands its input to run_emit with honest-observe's own
    boundaries. The event version and the auth and meta field names are the caller's, passed as
    data, not read from an injected object."""
    return await run_emit(event_type, aggregate_type, aggregate_id, payload, context, event_version, conn, new_event_id, event_timestamp, next_sequence, append_event, auth_fields, meta_fields)
