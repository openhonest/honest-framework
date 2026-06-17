"""Pure alerts logic."""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, TypedDict


class ActorRef(TypedDict):
    kind: str
    id: str
    tenant_id: str


class ChannelConfig(TypedDict):
    channel: str
    recipient_spec: ActorRef
    template_id: str
    delay_seconds: int


class EscalationRule(TypedDict):
    ttl_seconds: int
    escalate_to: ActorRef
    escalate_channel: str
    escalation_message_type: str


class AlertRoute(TypedDict):
    route_id: str
    message_type: str
    sender_type: str
    channels: list[ChannelConfig]
    escalation: EscalationRule | None
    priority: int


class Message(TypedDict):
    message_id: str
    message_type: str
    sender: ActorRef
    recipient: ActorRef
    channel: str
    payload: dict[str, Any]
    reply_required: bool
    resume_token: str
    ack_scope: str
    sent_at: str


class DeliveryPlan(TypedDict):
    message_id: str
    route_id: str
    channel: str
    recipient: ActorRef
    deliver_at: int
    status: str


# --- Builders -------------------------------------------------------------


def build_message(
    message_type: str,
    sender: ActorRef,
    recipient: ActorRef,
    payload: dict[str, Any],
    channel: str = "dom",
    reply_required: bool = False,
    ack_scope: str = "session",
) -> Message:
    mid = str(uuid.uuid4())
    return Message(
        message_id=mid,
        message_type=message_type,
        sender=dict(sender),
        recipient=dict(recipient),
        channel=channel,
        payload=dict(payload),
        reply_required=reply_required,
        resume_token=generate_resume_token(mid),
        ack_scope=ack_scope,
        sent_at=_iso_now(),
    )


def generate_resume_token(message_id: str) -> str:
    return hashlib.sha256(f"resume:{message_id}".encode()).hexdigest()[:24]


# --- Routing --------------------------------------------------------------


def match_routes(
    message: Message,
    routing_table: list[AlertRoute],
) -> list[AlertRoute]:
    """Filter routes whose message_type and sender_type match, sorted by
    priority (higher = earlier).
    """
    matches = [
        r for r in routing_table
        if r["message_type"] == message["message_type"]
        and (r["sender_type"] in ("", message["sender"]["kind"]))
    ]
    return sorted(matches, key=lambda r: -r["priority"])


def supervise(
    message: Message,
    routing_table: list[AlertRoute],
) -> list[DeliveryPlan]:
    """Apply every matching route. Each route's channels produce one
    DeliveryPlan per channel.
    """
    plans: list[DeliveryPlan] = []
    now = int(time.time())
    for route in match_routes(message, routing_table):
        for ch in route["channels"]:
            plans.append(DeliveryPlan(
                message_id=message["message_id"],
                route_id=route["route_id"],
                channel=ch["channel"],
                recipient=dict(ch["recipient_spec"]),
                deliver_at=now + ch["delay_seconds"],
                status="pending",
            ))
    return plans


def apply_escalation(message: Message, rule: EscalationRule) -> Message:
    """Return a new escalation message with the escalation rule's properties."""
    return build_message(
        message_type=rule["escalation_message_type"],
        sender=message["sender"],
        recipient=dict(rule["escalate_to"]),
        payload={"original_message_id": message["message_id"],
                 "original_type": message["message_type"]},
        channel=rule["escalate_channel"],
        reply_required=message["reply_required"],
    )


# --- Mailbox projection ---------------------------------------------------


def mailbox(
    actor_ref: ActorRef,
    at_time: int,
    events: list[dict[str, Any]],
) -> list[Message]:
    """Pure projection over an event log. Returns messages whose recipient
    matches and which have not terminated.
    """
    by_id: dict[str, Message] = {}
    terminated: set[str] = set()
    for ev in events:
        etype = ev.get("event_type", "")
        payload = ev.get("payload", {})
        mid = payload.get("message_id")
        if not mid:
            continue
        if etype == "alert.sent":
            msg = payload.get("message")
            if isinstance(msg, dict):
                by_id[mid] = msg
        elif etype in ("alert.acknowledged", "alert.expired", "alert.actioned"):
            terminated.add(mid)
    return [
        msg for mid, msg in by_id.items()
        if mid not in terminated
        and msg.get("recipient", {}).get("id") == actor_ref["id"]
    ]


def is_terminated(
    message: Message,
    actor_ref: ActorRef,
    at_time: int,
    events: list[dict[str, Any]],
) -> bool:
    terminal = {"alert.acknowledged", "alert.expired", "alert.actioned", "alert.failed"}
    for ev in events:
        if ev.get("event_type") in terminal and ev.get("payload", {}).get("message_id") == message["message_id"]:
            return True
    return False


# --- Lifecycle transitions ------------------------------------------------


_LIFECYCLE_TABLE: dict[tuple[str, str], str] = {
    ("created",     "deliver"):     "delivered",
    ("delivered",   "read"):        "read",
    ("read",        "acknowledge"): "acknowledged",
    ("read",        "action"):      "actioned",
    ("delivered",   "acknowledge"): "acknowledged",
    ("delivered",   "action"):      "actioned",
    ("created",     "expire"):      "expired",
    ("delivered",   "expire"):      "expired",
    ("read",        "expire"):      "expired",
    ("created",     "fail"):        "failed",
    ("delivered",   "fail"):        "failed",
    ("delivered",   "escalate"):    "escalated",
    ("read",        "escalate"):    "escalated",
}


def transition_lifecycle(current_state: str, event_name: str) -> str:
    """Dict-lookup dispatch. Returns "" if transition is undefined."""
    return _LIFECYCLE_TABLE.get((current_state, event_name), "")


# --- helpers ---------------------------------------------------------------


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
