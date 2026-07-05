"""DOM actor surfaces (section 9): render a message as a server-rendered HTMX fragment.

When a message is addressed to a dom actor it renders as a visual surface declared by its dom_surface.
Rendering is pure: message in, HTML string out; serving the fragment over HTTP and the SSE stream that
pushes it (section 4.2) are the boundary's job. The surface type selects the renderer through a table,
not a branch: banner, toast, modal, and inline are cards; a badge is a count.

Each surface also carries a default termination (SURFACE_DEFAULT_TERMINATION), applied at send time by
build_message when the sender omits one. The reply endpoint (section 9.1) is handle_reply: it records
the reply and the acknowledgment and returns the empty fragment HTMX swaps in to remove the surface.

The fragment embeds only trusted identifiers (the message id, i18n label ids, and declared option ids);
no free user text is rendered, so no escaping is applied here. Reply buttons post the chosen option to
the reply endpoint as an HTMX form field.
"""

from honest_type import ok

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


async def handle_reply(message_id, option_id, reply_payload, actor_id, runtime):
    """The reply endpoint (section 9.1): record the chosen option as alert.replied and then
    alert.acknowledged, and return the empty fragment HTMX swaps in to remove the surface. I/O only
    through the injected runtime."""
    await runtime.emit("alert.replied", message_id, {"option_id": option_id, "actor_id": actor_id, "reply_payload": reply_payload})
    await runtime.emit("alert.acknowledged", message_id, {"message_id": message_id, "actor_id": actor_id})
    return ok({"fragment": ""})
