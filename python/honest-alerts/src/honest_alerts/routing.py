"""The routing table schema and its validators (section 5).

The routing table is a set of honest-persist records that declare how each message type is delivered.
There is no listener registry: no actor registers to receive messages, and routing is entirely
table-driven. These are the boundary validators for an AlertRoute (section 5.1) and its ChannelConfig
and EscalationRule sub-schemas. All pure, ok/err, composing the actor and channel validators of
sections 2-3. The supervisor (section 6) reads validated routes and matches them to a message; the
matching, wildcard handling, and priority ordering live there, not here.
"""

from honest_alerts.actors import ACTOR_TYPES, validate_actor_ref
from honest_alerts.message import CHANNELS
from honest_type import err, fault, ok

_CHANNEL_CONFIG_REQUIRED = ("channel",)
_ESCALATION_REQUIRED = ("ttl_seconds", "escalate_to")
_ALERT_ROUTE_REQUIRED = ("route_id", "message_type", "channels", "priority")


def validate_channel_config(config):
    """A ChannelConfig names a declared channel and, when present, a valid recipient_spec (section 5.1).
    template_id and delay_seconds are optional and unconstrained. Returns ok(config) or a client fault.
    Pure; a sub-schema's fault propagates unchanged."""
    missing = [field for field in _CHANNEL_CONFIG_REQUIRED if field not in config]
    if missing:
        return err(fault("incomplete_channel_config", f"a channel config is missing required fields: {missing}", "client", detail=missing))
    if config["channel"] not in CHANNELS:
        return err(fault("invalid_channel", f"'{config['channel']}' is not a declared channel", "client", detail=config["channel"]))
    if "recipient_spec" in config:
        recipient = validate_actor_ref(config["recipient_spec"])
        if "err" in recipient:
            return recipient
    return ok(config)


def validate_escalation_rule(rule):
    """An EscalationRule declares ttl_seconds and a valid escalate_to actor, and — when present — a
    declared escalate_channel (section 5.1). escalation_message_type is optional and unconstrained.
    Returns ok(rule) or a client fault. Pure."""
    missing = [field for field in _ESCALATION_REQUIRED if field not in rule]
    if missing:
        return err(fault("incomplete_escalation", f"an escalation rule is missing required fields: {missing}", "client", detail=missing))
    escalate_to = validate_actor_ref(rule["escalate_to"])
    if "err" in escalate_to:
        return escalate_to
    if "escalate_channel" in rule and rule["escalate_channel"] not in CHANNELS:
        return err(fault("invalid_channel", f"'{rule['escalate_channel']}' is not a declared channel", "client", detail=rule["escalate_channel"]))
    return ok(rule)


def validate_alert_route(route):
    """An AlertRoute declares route_id, message_type, channels, and priority; a sender_type, when
    present, is a declared actor type; every channel config is valid; and an escalation, when present,
    is valid (section 5.1). Returns ok(route) or the first client fault. Pure; a sub-schema's fault
    propagates unchanged. Independent guards, not a discriminant dispatch."""
    missing = [field for field in _ALERT_ROUTE_REQUIRED if field not in route]
    if missing:
        return err(fault("incomplete_route", f"an alert route is missing required fields: {missing}", "client", detail=missing))
    if "sender_type" in route and route["sender_type"] not in ACTOR_TYPES:
        return err(fault("invalid_actor_type", f"'{route['sender_type']}' is not a declared actor type", "client", detail=route["sender_type"]))
    for config in route["channels"]:
        checked = validate_channel_config(config)
        if "err" in checked:
            return checked
    if "escalation" in route:
        escalation = validate_escalation_rule(route["escalation"])
        if "err" in escalation:
            return escalation
    return ok(route)
