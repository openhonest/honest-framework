"""honest-alerts: actor-model message passing (section 1).

Messages pass between actors; no actor shares state with another. A message lands in a recipient's
mailbox and persists there until a declared termination condition is met. The pure core recognizes and
validates envelopes, routes a message to its channels, and projects the mailbox as a fold over
honest-observe's event log. The module owns its boundaries: the clock and a random source, the routing
table and the delivery queue in honest-persist, the alert events in honest-observe, and the six
delivery channels on the network. The orchestrators run one path each, and the doors are what the world
calls. No capability is handed in as an object.
"""

from honest_alerts.actors import ACTOR_TYPES, validate_actor_ref
from honest_alerts.boundaries import (
    await_reply,
    deliver_dom,
    deliver_posted,
    emit_event,
    mark_delivery,
    new_message_id,
    new_resume_token,
    now,
    read_events,
    read_pending,
    read_raw_config,
    read_routes,
    write_delivery,
)
from honest_alerts.config import ALERT_CONFIG_DEFAULTS, load_config, resolve_config, start
from honest_alerts.dispatch import build_message, run_send, run_send_and_wait, send, send_and_wait
from honest_alerts.events import ALERT_AGGREGATE, ALERT_EVENTS, alert_event
from honest_alerts.lifecycle import LIFECYCLE_EVENTS, advance, alert_lifecycle
from honest_alerts.mailbox import ACK_SCOPES, TERMINATION_CONDITIONS, is_terminated, mailbox, recipient_matches
from honest_alerts.message import CHANNELS, DOM_SURFACES, REPLY_STYLES, validate_message, validate_reply_option, validate_termination
from honest_alerts.routing import validate_alert_route, validate_channel_config, validate_escalation_rule
from honest_alerts.supervisor import delivery_plan, matching_routes, message_type_matches, run_deliveries, tick
from honest_alerts.surfaces import SURFACE_DEFAULT_TERMINATION, handle_reply, record_reply, render_mailbox, render_surface, serve_mailbox

__all__ = [
    # Pure core
    "build_message",
    "validate_message",
    "validate_actor_ref",
    "validate_termination",
    "validate_reply_option",
    "validate_channel_config",
    "validate_escalation_rule",
    "validate_alert_route",
    "advance",
    "message_type_matches",
    "matching_routes",
    "delivery_plan",
    "alert_event",
    "mailbox",
    "is_terminated",
    "recipient_matches",
    "render_surface",
    "resolve_config",
    # Readers
    "now",
    "new_message_id",
    "new_resume_token",
    "read_routes",
    "read_pending",
    "read_events",
    "await_reply",
    "read_raw_config",
    # Output boundaries
    "write_delivery",
    "mark_delivery",
    "emit_event",
    "deliver_dom",
    "deliver_posted",
    # Orchestrators
    "run_send",
    "run_send_and_wait",
    "run_deliveries",
    "record_reply",
    "render_mailbox",
    "load_config",
    # Doors
    "send",
    "send_and_wait",
    "handle_reply",
    "serve_mailbox",
    "tick",
    "start",
    # Vocabularies and tables
    "TERMINATION_CONDITIONS",
    "ACK_SCOPES",
    "ACTOR_TYPES",
    "DOM_SURFACES",
    "REPLY_STYLES",
    "CHANNELS",
    "LIFECYCLE_EVENTS",
    "alert_lifecycle",
    "ALERT_AGGREGATE",
    "ALERT_EVENTS",
    "ALERT_CONFIG_DEFAULTS",
    "SURFACE_DEFAULT_TERMINATION",
]
