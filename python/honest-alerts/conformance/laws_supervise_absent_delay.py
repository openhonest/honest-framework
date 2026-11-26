# scenario: supervise delivers immediately for an absent channel delay
# inherits: hd=python/honest-alerts/honest-alerts.hd::supervise -> feature=specs/features/honest-alerts.feature::supervise delivers immediately for an absent channel delay
"""A matching channel with an explicit absent delay is delivered immediately."""

from honest_alerts import supervise

_RECIPIENT = {"type": "user", "id": "u1", "tenant_id": None}
_MESSAGE_ID = "0192f000-0000-7000-8000-000000000001"
_MESSAGE = {
    "message_id": _MESSAGE_ID,
    "message_type": "order.placed",
    "message_version": "1",
    "sender": {"type": "framework", "id": None, "tenant_id": None},
    "recipient": _RECIPIENT,
    "subject_label_id": "alerts.order_placed",
    "body_label_id": None,
    "channel": None,
    "payload": {},
    "dom_surface": None,
    "dom_target": None,
    "reply_required": False,
    "reply_options": None,
    "resume_token": None,
    "termination": {"condition": "never", "ttl_seconds": None, "event_type": None, "event_filter": None},
    "ack_scope": "actor",
    "sent_at": 1000,
}
_ROUTES = [
    {
        "route_id": "r1",
        "message_type": "order.placed",
        "sender_type": None,
        "channels": [
            {"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": None},
        ],
        "escalation": None,
        "priority": 1,
    },
]
_EXPECTED = {
    "deliveries": [
        {
            "message_id": _MESSAGE_ID,
            "route_id": "r1",
            "channel": "dom",
            "recipient": _RECIPIENT,
            "deliver_at": 1000,
            "status": "pending",
        },
    ],
}


def probe_supervise_absent_delay():
    """An absent delay preserves sent_at as the delivery time."""
    try:
        got = supervise(_MESSAGE, _ROUTES)
    except TypeError as exc:
        return [f"supervise raised instead of delivering immediately: {exc}"]
    if got != _EXPECTED:
        return [f"supervise returned {got!r}, expected {_EXPECTED!r}"]
    return []
