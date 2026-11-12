"""DOM actor surfaces and the reply endpoint (sections 9, 9.1).

Rendering is pure: a message in, an HTML string out; the surface type selects the renderer through a
table, not a branch. render_mailbox is the orchestrator that reads an actor's events, projects the
pending messages, and renders each. record_reply is the orchestrator that records a reply as
alert.replied then alert.acknowledged. Both take the boundaries they touch as arguments; the doors
serve_mailbox and handle_reply wire the module's own boundaries and hand off to them.
"""

from honest_type import ok

from honest_alerts import boundaries
from honest_alerts.events import alert_event
from honest_alerts.mailbox import mailbox

# The termination each surface defaults to when the sender does not declare one (section 9). Its keys
# are exactly the DOM surfaces (pinned by the surface_defaults law). "Persists until dismissed" for the
# badge is read as acknowledged: the dismissal is the acknowledgment.
SURFACE_DEFAULT_TERMINATION = {
    "banner": {"condition": "acknowledged"},
    "toast": {"condition": "ttl", "ttl_seconds": 5},
    "modal": {"condition": "acknowledged"},
    "badge": {"condition": "acknowledged"},
    "inline": {"condition": "acknowledged"},
}


def _render_card(message):
    """A card surface (banner, toast, modal, inline): the subject, an optional body, and a reply button
    per declared reply option, wrapped in a surface-classed div carrying the message id (section 9)."""
    mid = message["message_id"]
    surface = message["dom_surface"]
    body = f'<span class="alert-body" data-label="{message["body_label_id"]}"></span>' if "body_label_id" in message else ""
    buttons = "".join(
        f'<button class="alert-action" hx-post="/api/alerts/{mid}/reply" name="option_id" value="{option["option_id"]}" data-label="{option["label_id"]}"></button>'
        for option in message.get("reply_options", [])
    )
    return (
        f'<div class="alert alert-{surface}" data-message-id="{mid}" data-surface="{surface}">'
        f'<span class="alert-subject" data-label="{message["subject_label_id"]}"></span>'
        f"{body}{buttons}</div>"
    )


def _render_badge(message):
    """A badge surface: a numeric indicator on a nav element carrying the message id and subject
    (section 9). A single message renders as a count of one; an aggregate count is a mailbox concern."""
    mid = message["message_id"]
    return f'<span class="alert-badge" data-message-id="{mid}" data-surface="badge" data-label="{message["subject_label_id"]}">1</span>'


_SURFACE_RENDERERS = {
    "banner": _render_card,
    "toast": _render_card,
    "modal": _render_card,
    "inline": _render_card,
    "badge": _render_badge,
}


def render_surface(message):
    """Render a message as its declared DOM surface (section 9). Pure: the dom_surface selects the
    renderer through _SURFACE_RENDERERS. The dom_surface is a declared one (validated at build time)."""
    return _SURFACE_RENDERERS[message["dom_surface"]](message)


async def render_mailbox(actor_ref, at_time, conn, read_events):
    """Render an actor's pending messages (sections 4, 9): read the actor's events, project the pending
    messages, and render each as its surface. I/O only through the handed-in read_events boundary."""
    events = await read_events(conn, actor_ref)
    pending = mailbox(actor_ref, events, at_time)
    return "".join(render_surface(event["payload"]) for event in pending)


async def record_reply(message_id, option_id, reply_payload, actor_id, conn, emit_event):
    """Record a reply (section 9.1): emit alert.replied with the chosen option, then alert.acknowledged.
    Returns ok({fragment}) with the empty fragment HTMX swaps in to remove the surface. I/O only through
    the handed-in emit_event boundary."""
    await emit_event(alert_event("alert.replied", message_id, {"option_id": option_id, "actor_id": actor_id, "reply_payload": reply_payload}), conn)
    await emit_event(alert_event("alert.acknowledged", message_id, {"message_id": message_id, "actor_id": actor_id}), conn)
    return ok({"fragment": ""})


async def serve_mailbox(actor_ref, at_time, conn):
    """The door for the mailbox route (section 9): hand the request to render_mailbox with the module's
    own read_events boundary."""
    return await render_mailbox(actor_ref, at_time, conn, boundaries.read_events)


async def handle_reply(message_id, option_id, reply_payload, actor_id, conn):
    """The door for the reply route (section 9.1): hand the reply to record_reply with the module's own
    emit_event boundary."""
    return await record_reply(message_id, option_id, reply_payload, actor_id, conn, boundaries.emit_event)
