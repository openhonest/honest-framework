"""The message envelope and its sub-schemas (section 3).

A message is an immutable, typed record. Every field that affects delivery, persistence, or lifecycle is
declared at send time; nothing about behaviour is implicit. These are the boundary validators for the
envelope (section 3.1), the reply options (section 3.2), and the termination spec (section 3.3), plus
the DOM surface and reply-style vocabularies (sections 9, 3.2). All pure, returning ok/err.

Which fields a termination requires depends on its condition; that dependency is data (a required-field
table keyed by condition), not an if/elif chain — the same discipline the mailbox's dispatch tables use.
"""

from honest_alerts.mailbox import ACK_SCOPES, TERMINATION_CONDITIONS
from honest_alerts.actors import validate_actor_ref
from honest_type import err, fault, ok

DOM_SURFACES = frozenset({"banner", "toast", "modal", "badge", "inline"})
REPLY_STYLES = frozenset({"primary", "secondary", "danger", "warning"})
# The message's preferred delivery channel (section 3.1), the full delivery set shared with the routing
# table's ChannelConfig (section 5.1).
CHANNELS = frozenset({"dom", "email", "sms", "webhook", "slack", "teams"})

# The extra fields each termination condition requires beyond `condition` (section 3.3). Keyed by
# condition so the check is a table lookup, never a branch on the condition value. Its keys must equal
# TERMINATION_CONDITIONS (pinned by the validate_termination law).
_TERMINATION_REQUIRED = {
    "ttl": ("ttl_seconds",),
    "acknowledged": (),
    "event": ("event_type",),
    "never": (),
}

_REPLY_OPTION_REQUIRED = ("option_id", "label_id")

# The non-optional fields of the message envelope (section 3.1). The optional fields — channel,
# body_label_id, dom_surface, dom_target, reply_options, resume_token — are validated when present.
_MESSAGE_REQUIRED = (
    "message_id",
    "message_type",
    "message_version",
    "sender",
    "recipient",
    "subject_label_id",
    "payload",
    "reply_required",
    "termination",
    "ack_scope",
    "sent_at",
)


def validate_termination(spec):
    """A TerminationSpec names a declared condition and carries that condition's required fields
    (section 3.3). Returns ok(spec) or a client fault. Pure."""
    condition = spec.get("condition")
    if condition not in TERMINATION_CONDITIONS:
        return err(fault("invalid_termination", f"'{condition}' is not a declared termination condition", "client", detail=condition))
    missing = [field for field in _TERMINATION_REQUIRED[condition] if field not in spec]
    if missing:
        return err(fault("incomplete_termination", f"a '{condition}' termination is missing required fields: {missing}", "client", detail=missing))
    return ok(spec)


def validate_reply_option(option):
    """A ReplyOption declares option_id and label_id, and a style, when present, is a declared one
    (section 3.2). Returns ok(option) or a client fault. Pure."""
    missing = [field for field in _REPLY_OPTION_REQUIRED if field not in option]
    if missing:
        return err(fault("incomplete_reply_option", f"a reply option is missing required fields: {missing}", "client", detail=missing))
    if "style" in option and option["style"] not in REPLY_STYLES:
        return err(fault("invalid_reply_style", f"'{option['style']}' is not a declared reply style", "client", detail=option["style"]))
    return ok(option)


def validate_message(message):
    """A Message carries every required envelope field, valid sender and recipient references, a valid
    termination, a declared ack_scope, and — when present — a declared dom_surface and valid reply
    options (section 3.1). Returns ok(message) or the first client fault. Pure. Independent guards, not
    a discriminant dispatch; a sub-schema's fault is propagated unchanged."""
    missing = [field for field in _MESSAGE_REQUIRED if field not in message]
    if missing:
        return err(fault("incomplete_message", f"message is missing required fields: {missing}", "client", detail=missing))
    sender = validate_actor_ref(message["sender"])
    if "err" in sender:
        return sender
    recipient = validate_actor_ref(message["recipient"])
    if "err" in recipient:
        return recipient
    termination = validate_termination(message["termination"])
    if "err" in termination:
        return termination
    if message["ack_scope"] not in ACK_SCOPES:
        return err(fault("invalid_ack_scope", f"'{message['ack_scope']}' is not a declared ack scope", "client", detail=message["ack_scope"]))
    if "channel" in message and message["channel"] not in CHANNELS:
        return err(fault("invalid_channel", f"'{message['channel']}' is not a declared channel", "client", detail=message["channel"]))
    if "dom_surface" in message and message["dom_surface"] not in DOM_SURFACES:
        return err(fault("invalid_dom_surface", f"'{message['dom_surface']}' is not a declared DOM surface", "client", detail=message["dom_surface"]))
    for option in message.get("reply_options", []):
        checked = validate_reply_option(option)
        if "err" in checked:
            return checked
    return ok(message)
