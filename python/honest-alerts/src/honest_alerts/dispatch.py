"""send and send_and_wait: the send API (section 8).

send is fire-and-forget; send_and_wait suspends the caller until a reply arrives or the wait times out,
on the language's native async, holding no thread. Both assemble a message and hand it to send_message,
which validates it (section 3) and routes it through the supervisor (section 6).

The pure part is build_message: it assembles the section 3.1 envelope from the send arguments, injecting
the message id and send time (both I/O) as values. Everything else that touches the world — the id, the
clock, the resume token, the routing-table read, and the reply wait — reaches it through the injected
runtime, the same discipline the supervisor uses.

The runtime the boundaries expect (in addition to the supervisor's now/insert/emit):
  message_id()                       -> str    (a fresh message id)
  resume_token()                     -> str    (a fresh reply-correlation token)
  await routes()                     -> [AlertRoute]   (the routing table)
  await wait_for_reply(id, timeout)  -> reply | None   (the reply event, or None on timeout)
"""

from honest_type import ok

from honest_alerts.message import validate_message
from honest_alerts.supervisor import supervise

# The optional envelope fields carried straight through from opts when present (section 3.1).
_OPTIONAL_FIELDS = ("channel", "body_label_id", "dom_surface", "dom_target", "reply_options", "resume_token")


def build_message(message_type, recipient, payload, opts, context, message_id, sent_at):
    """Assemble a section 3.1 message envelope from the send arguments (section 8). Pure — the id and
    send time are injected, not read. The sender is the one named in opts, else the request context's
    actor, else the framework itself; message_version, subject_label_id, reply_required, and ack_scope
    take spec defaults; termination and the optional surface fields come from opts."""
    message = {
        "message_id": message_id,
        "message_type": message_type,
        "message_version": opts.get("message_version", "1"),
        "sender": opts.get("sender") or context.get("actor") or {"type": "framework"},
        "recipient": recipient,
        "subject_label_id": opts.get("subject_label_id", message_type),
        "payload": payload,
        "reply_required": opts.get("reply_required", False),
        "termination": opts.get("termination", {}),
        "ack_scope": opts.get("ack_scope", "actor"),
        "sent_at": sent_at,
    }
    for field in _OPTIONAL_FIELDS:
        if field in opts:
            message[field] = opts[field]
    return message


async def send_message(message, runtime):
    """Validate a built message and route it through the supervisor (section 8). Returns
    ok({message_id, delivered}), or the validation fault if the message is malformed (nothing is
    dispatched). I/O only through the injected runtime."""
    valid = validate_message(message)
    if "err" in valid:
        return valid
    routing_table = await runtime.routes()
    result = await supervise(message, routing_table, runtime)
    return ok({"message_id": message["message_id"], "delivered": result["ok"]["delivered"]})


async def send(message_type, recipient, payload, opts, context, runtime):
    """Send a message, fire and forget (section 8.1). Build the envelope with the runtime's id and time,
    then dispatch it. Returns send_message's result."""
    message = build_message(message_type, recipient, payload, opts, context, runtime.message_id(), runtime.now())
    return await send_message(message, runtime)


async def send_and_wait(message_type, recipient, payload, opts, context, runtime):
    """Send a message and suspend until a reply arrives or the wait times out (section 8.2, 8.3). The
    message is marked reply_required and carries a fresh resume token. Returns ok({status: "replied",
    option_id, actor_id, payload}) on a reply, ok({status: "timeout"}) on timeout, or the validation
    fault if the message is malformed. No thread is held during the wait."""
    reply_opts = {**opts, "reply_required": True, "resume_token": runtime.resume_token()}
    message = build_message(message_type, recipient, payload, reply_opts, context, runtime.message_id(), runtime.now())
    sent = await send_message(message, runtime)
    if "err" in sent:
        return sent
    reply = await runtime.wait_for_reply(message["message_id"], opts.get("termination", {}).get("ttl_seconds"))
    if reply is None:
        return ok({"status": "timeout"})
    return ok({"status": "replied", "option_id": reply["option_id"], "actor_id": reply["actor_id"], "payload": reply["reply_payload"]})
