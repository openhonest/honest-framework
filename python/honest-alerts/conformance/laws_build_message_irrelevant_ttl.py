# scenario: build_message rejects an irrelevant ttl for never termination
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message rejects an irrelevant ttl for never termination
"""A never termination must have an absent ttl_seconds field."""

from honest_alerts import build_message

_GIVEN = {
    "message_type": "order.placed",
    "recipient": {"type": "user", "id": "u1", "tenant_id": None},
    "payload": {},
    "opts": {
        "message_version": "1",
        "subject_label_id": "alerts.order_placed",
        "body_label_id": None,
        "channel": None,
        "dom_surface": None,
        "dom_target": None,
        "reply_options": None,
        "termination": {"condition": "never", "ttl_seconds": 10, "event_type": None, "event_filter": None},
        "ack_scope": "actor",
    },
    "sender": {"type": "framework", "id": None, "tenant_id": None},
    "message_id": "0192f000-0000-7000-8000-000000000001",
    "sent_at": 1000,
    "reply_required": False,
    "registered": {"message_type": "order.placed", "message_versions": ["1"]},
}


def probe_build_message_irrelevant_ttl():
    """Reject the populated irrelevant TTL as an invalid-termination client fault."""
    got = build_message(**_GIVEN)
    actual = (got.get("is_err"), got.get("code"), got.get("category"))
    expected = (True, "invalid_termination", "client")
    if actual != expected:
        return [f"build_message returned {got!r}, expected invalid_termination client Fault"]
    return []
