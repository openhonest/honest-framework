"""honest-alerts - the message-passing layer (unit 1): an actor model where messages pass between
actors through three doors (send, acknowledge, register_message_type), land in a delivery queue, and
persist until a declared termination condition is met. Mailboxes are pure projections over the
honest-observe event log, reached by import, never a door (honest-alerts.hd, section 1, 4.1).

The wildcard exports are send, acknowledge, register_message_type, advance, mailbox,
is_terminated, and alert_tables_schema. Other existing bindings are available through
explicit named imports.
"""

from honest_alerts.faults import alert_tables_schema, alerts_fault
from honest_alerts.pure import (
    NOTHING,
    advance,
    build_ack_event,
    build_message,
    build_registered_type,
    is_terminated,
    mailbox,
    supervise,
    terminated_actor,
    terminated_broadcast,
    terminated_session,
)
from honest_alerts.boundary import (
    acknowledge,
    emit,
    new_message_id,
    now,
    read_registered_type,
    read_routes,
    register_message_type,
    run_acknowledge,
    run_register_message_type,
    run_send,
    send,
    write_delivery,
    write_registered_type,
)

# inherits: hd=python/honest-alerts/honest-alerts.hd::send -> feature=specs/features/honest-alerts.feature::send is available as an honest_alerts public export -> test=python/honest-alerts/conformance/laws_send_public_export.py::probe_send_public_export
__all__ = [
    "send",
    "acknowledge",
    "register_message_type",
    "advance",
    "mailbox",
    "is_terminated",
    "alert_tables_schema",
]
