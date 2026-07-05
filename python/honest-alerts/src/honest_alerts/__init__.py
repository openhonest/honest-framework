"""honest-alerts: actor-model message passing (section 1).

Messages pass between actors; no actor shares state with another. A message lands in a recipient's
mailbox and persists there until a declared termination condition is met. Implemented so far: the actor
identity model and the message envelope with its sub-schemas (sections 2-3) as vocabularies and pure
validators, and the mailbox projection and message termination (section 4) as pure folds over
honest-observe's event log. Both the termination condition and the acknowledgment scope are dispatched
through tables rather than if/elif chains. The delivery boundaries (supervisor, channel handlers,
send/send_and_wait) build on this pure core.
"""

from honest_alerts.actors import ACTOR_TYPES, validate_actor_ref
from honest_alerts.dispatch import build_message, send, send_and_wait, send_message
from honest_alerts.mailbox import ACK_SCOPES, TERMINATION_CONDITIONS, is_terminated, mailbox, recipient_matches
from honest_alerts.message import CHANNELS, DOM_SURFACES, REPLY_STYLES, validate_message, validate_reply_option, validate_termination
from honest_alerts.routing import validate_alert_route, validate_channel_config, validate_escalation_rule
from honest_alerts.lifecycle import LIFECYCLE_EVENTS, advance, alert_lifecycle
from honest_alerts.supervisor import delivery_plan, execute_deliveries, matching_routes, message_type_matches, supervise
from honest_alerts.surfaces import SURFACE_DEFAULT_TERMINATION, handle_reply, render_surface

__all__ = [
    "mailbox",
    "is_terminated",
    "recipient_matches",
    "TERMINATION_CONDITIONS",
    "ACK_SCOPES",
    "ACTOR_TYPES",
    "validate_actor_ref",
    "DOM_SURFACES",
    "REPLY_STYLES",
    "CHANNELS",
    "validate_termination",
    "validate_reply_option",
    "validate_message",
    "validate_channel_config",
    "validate_escalation_rule",
    "validate_alert_route",
    "message_type_matches",
    "matching_routes",
    "delivery_plan",
    "supervise",
    "execute_deliveries",
    "alert_lifecycle",
    "LIFECYCLE_EVENTS",
    "advance",
    "build_message",
    "send_message",
    "send",
    "send_and_wait",
    "SURFACE_DEFAULT_TERMINATION",
    "render_surface",
    "handle_reply",
]
