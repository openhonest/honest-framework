"""honest-alerts: actor-model message passing (section 1).

Messages pass between actors; no actor shares state with another. A message lands in a recipient's
mailbox and persists there until a declared termination condition is met. Implemented so far: the
mailbox projection and message termination (section 4) — pure folds over honest-observe's event log,
with the termination condition and the acknowledgment scope each dispatched through a table rather than
an if/elif chain. The delivery boundaries (supervisor, channel handlers, send/send_and_wait) build on
this pure core.
"""

from honest_alerts.mailbox import ACK_SCOPES, TERMINATION_CONDITIONS, is_terminated, mailbox, recipient_matches

__all__ = [
    "mailbox",
    "is_terminated",
    "recipient_matches",
    "TERMINATION_CONDITIONS",
    "ACK_SCOPES",
]
