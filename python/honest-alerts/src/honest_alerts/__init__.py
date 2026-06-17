"""honest-alerts — actor-model messaging.

build_message + supervise + match_routes → delivery plans.
mailbox(actor, events) → list of messages currently addressed to the actor.
transition_lifecycle → updates message state through delivered/read/actioned.
"""
from honest_alerts.core import (
    ActorRef,
    AlertRoute,
    ChannelConfig,
    DeliveryPlan,
    EscalationRule,
    Message,
    apply_escalation,
    build_message,
    generate_resume_token,
    is_terminated,
    mailbox,
    match_routes,
    supervise,
    transition_lifecycle,
)

__all__ = [
    "ActorRef",
    "AlertRoute",
    "ChannelConfig",
    "DeliveryPlan",
    "EscalationRule",
    "Message",
    "apply_escalation",
    "build_message",
    "generate_resume_token",
    "is_terminated",
    "mailbox",
    "match_routes",
    "supervise",
    "transition_lifecycle",
]
