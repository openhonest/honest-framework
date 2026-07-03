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
from honest_alerts.mailbox import ACK_SCOPES, TERMINATION_CONDITIONS, is_terminated, mailbox, recipient_matches
from honest_alerts.message import DOM_SURFACES, REPLY_STYLES, validate_message, validate_reply_option, validate_termination

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
    "validate_termination",
    "validate_reply_option",
    "validate_message",
]
