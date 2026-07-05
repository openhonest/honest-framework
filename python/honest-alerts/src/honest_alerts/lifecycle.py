"""The message lifecycle state machine (section 7).

Every message instance moves through a lifecycle: created, then delivered/read/escalated on the way to
one of the terminal states (acknowledged, actioned, expired, failed). The machine is honest-type's pure
state machine: a (state, event) -> next-state table, no execution engine of its own (section 1.2).

Each successful transition also names the honest-observe event it produces (alert.delivered, alert.read,
and so on), which feeds back into the mailbox projection (section 4). advance() is the pure step: it
applies one event to alert_lifecycle and, on success, returns the next state together with that event.
"""

from honest_type import ok, state_machine, transition, vocabulary

alert_lifecycle = state_machine(
    states=vocabulary(
        {"alert_state": {"created", "delivered", "read", "acknowledged", "actioned", "escalated", "expired", "failed"}}
    ),
    events=vocabulary({"alert_event": {"deliver", "read", "acknowledge", "action", "escalate", "expire", "fail"}}),
    transitions={
        ("created", "deliver"): "delivered",
        ("created", "fail"): "failed",
        ("created", "expire"): "expired",
        ("delivered", "read"): "read",
        ("delivered", "acknowledge"): "acknowledged",
        ("delivered", "action"): "actioned",
        ("delivered", "escalate"): "escalated",
        ("delivered", "expire"): "expired",
        ("read", "acknowledge"): "acknowledged",
        ("read", "action"): "actioned",
        ("read", "escalate"): "escalated",
        ("read", "expire"): "expired",
        ("escalated", "acknowledge"): "acknowledged",
        ("escalated", "action"): "actioned",
        ("escalated", "expire"): "expired",
    },
    initial="created",
    terminal=["acknowledged", "actioned", "expired", "failed"],
)

# The honest-observe event each lifecycle event produces (section 7). Its keys are exactly the machine's
# events (pinned by the lifecycle_events law), so a table lookup, not a branch, names the event.
LIFECYCLE_EVENTS = {
    "deliver": "alert.delivered",
    "read": "alert.read",
    "acknowledge": "alert.acknowledged",
    "action": "alert.actioned",
    "escalate": "alert.escalated",
    "expire": "alert.expired",
    "fail": "alert.failed",
}


def advance(current_state, event):
    """Apply one lifecycle event to alert_lifecycle (section 7). On success, return the next state and
    the honest-observe event the transition produces; otherwise return the transition fault (an
    undeclared event, or no transition from the current state). Pure — the caller stores the state."""
    result = transition(alert_lifecycle, current_state, event)
    if "err" in result:
        return result
    return ok({"state": result["ok"]["state"], "event": LIFECYCLE_EVENTS[event]})
