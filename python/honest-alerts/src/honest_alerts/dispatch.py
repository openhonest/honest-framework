"""The send API (section 8): build an envelope, route it, queue its deliveries, and for send_and_wait,
await the reply.

build_message is pure: it assembles the section 3.1 envelope from the send arguments, taking the
message id and send time as values. run_send and run_send_and_wait are the orchestrators, one per
path, flat and never calling each other. Each takes the boundaries it touches as arguments, so a test
drives it with stand-ins; the doors send and send_and_wait wire the module's own boundaries and hand
off to them.
"""

from honest_type import ok

from honest_alerts import boundaries
from honest_alerts.events import alert_event
from honest_alerts.message import validate_message
from honest_alerts.routing import validate_alert_route
from honest_alerts.supervisor import delivery_plan, matching_routes
from honest_alerts.surfaces import SURFACE_DEFAULT_TERMINATION

# The optional envelope fields carried straight through from opts when present (section 3.1).
_OPTIONAL_FIELDS = ("channel", "body_label_id", "dom_surface", "dom_target", "reply_options", "resume_token")


def build_message(message_type, recipient, payload, opts, context, message_id, sent_at):
    """Assemble a section 3.1 message envelope from the send arguments (section 8). Pure — the id and
    send time are injected, not read. The sender is the one named in opts, else the request context's
    actor, else the framework itself; message_version, subject_label_id, reply_required, and ack_scope
    take spec defaults; termination comes from opts, or the dom_surface's default termination (section 9)
    when opts omits it; the optional surface fields come from opts."""
    message = {
        "message_id": message_id,
        "message_type": message_type,
        "message_version": opts.get("message_version", "1"),
        "sender": opts.get("sender") or context.get("actor") or {"type": "framework"},
        "recipient": recipient,
        "subject_label_id": opts.get("subject_label_id", message_type),
        "payload": payload,
        "reply_required": opts.get("reply_required", False),
        "termination": opts.get("termination") or SURFACE_DEFAULT_TERMINATION.get(opts.get("dom_surface"), {}),
        "ack_scope": opts.get("ack_scope", "actor"),
        "sent_at": sent_at,
    }
    for field in _OPTIONAL_FIELDS:
        if field in opts:
            message[field] = opts[field]
    return message


async def run_send(message_type, recipient, payload, opts, context, conn, new_message_id, now, read_routes, write_delivery, emit_event):
    """Build, validate, route, and queue a message (section 8.1). Returns ok({message_id, delivered}),
    or the first client fault, with nothing queued. No route emits alert.no_route and delivers nothing;
    otherwise it writes one pending delivery per channel and emits alert.sent."""
    sent_at = now()
    message = build_message(message_type, recipient, payload, opts, context, new_message_id(), sent_at)
    valid = validate_message(message)
    if "err" in valid:
        return valid
    routes = await read_routes(conn)
    for route in routes:
        checked = validate_alert_route(route)
        if "err" in checked:
            return checked
    matched = matching_routes(routes, message)
    if not matched:
        await emit_event(alert_event("alert.no_route", message["message_id"], {"message_type": message_type}), conn)
        return ok({"message_id": message["message_id"], "delivered": 0})
    plan = delivery_plan(message, matched, sent_at)
    for delivery in plan:
        await write_delivery(delivery, conn)
    await emit_event(alert_event("alert.sent", message["message_id"], message), conn)
    return ok({"message_id": message["message_id"], "delivered": len(plan)})


async def run_send_and_wait(message_type, recipient, payload, opts, context, conn, new_message_id, new_resume_token, now, read_routes, write_delivery, emit_event, await_reply):
    """Send a message marked reply-required and suspend until a reply arrives or the wait times out
    (section 8.2, 8.3). Returns ok({status: "replied", ...}) on a reply, ok({status: "timeout"}) on
    timeout, ok({status: "no_route"}) when nothing routes, or a client fault. No thread is held."""
    sent_at = now()
    reply_opts = {**opts, "reply_required": True, "resume_token": new_resume_token()}
    message = build_message(message_type, recipient, payload, reply_opts, context, new_message_id(), sent_at)
    valid = validate_message(message)
    if "err" in valid:
        return valid
    routes = await read_routes(conn)
    for route in routes:
        checked = validate_alert_route(route)
        if "err" in checked:
            return checked
    matched = matching_routes(routes, message)
    if not matched:
        await emit_event(alert_event("alert.no_route", message["message_id"], {"message_type": message_type}), conn)
        return ok({"status": "no_route"})
    plan = delivery_plan(message, matched, sent_at)
    for delivery in plan:
        await write_delivery(delivery, conn)
    await emit_event(alert_event("alert.sent", message["message_id"], message), conn)
    reply = await await_reply(conn, message["message_id"], opts.get("termination", {}).get("ttl_seconds"))
    if reply is None:
        return ok({"status": "timeout"})
    return ok({"status": "replied", "option_id": reply["option_id"], "actor_id": reply["actor_id"], "payload": reply["reply_payload"]})


async def send(message_type, recipient, payload, opts, context, conn):
    """The door for fire-and-forget send (section 8.1): hand the arguments to run_send with the
    module's own boundaries."""
    return await run_send(message_type, recipient, payload, opts, context, conn, boundaries.new_message_id, boundaries.now, boundaries.read_routes, boundaries.write_delivery, boundaries.emit_event)


async def send_and_wait(message_type, recipient, payload, opts, context, conn):
    """The door for send-and-wait (section 8.2): hand the arguments to run_send_and_wait with the
    module's own boundaries."""
    return await run_send_and_wait(message_type, recipient, payload, opts, context, conn, boundaries.new_message_id, boundaries.new_resume_token, boundaries.now, boundaries.read_routes, boundaries.write_delivery, boundaries.emit_event, boundaries.await_reply)
