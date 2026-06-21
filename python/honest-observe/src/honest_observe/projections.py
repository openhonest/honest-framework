"""Projections (section 6): the only way to read the log — a pure fold over filtered events.

A projection filters the event log by type, aggregate, and time window, then folds the matching
events into a derived read model with a pure `(state, event) -> state` function. `apply_projection`
is pure: it takes the events as data and never reads the log itself — pulling the events from the
log is the boundary's concern. No I/O, no mutation of the inputs.
"""


def matches(event, event_types=None, aggregate_type=None, aggregate_id=None, from_ts=None, to_ts=None):
    """Whether an event passes a projection's filters (section 6.1). Pure. The time window is
    half-open: `from_ts` inclusive, `to_ts` exclusive. A `None` filter does not constrain."""
    if event_types is not None and event["event_type"] not in event_types:
        return False
    if aggregate_type is not None and event.get("aggregate_type") != aggregate_type:
        return False
    if aggregate_id is not None and event.get("aggregate_id") != aggregate_id:
        return False
    if from_ts is not None and event["timestamp"] < from_ts:
        return False
    if to_ts is not None and event["timestamp"] >= to_ts:
        return False
    return True


def apply_projection(events, fold, initial_state, event_types=None, aggregate_type=None, aggregate_id=None, from_ts=None, to_ts=None):
    """Fold the matching events into a derived read model (section 6). Pure: filter `events` by
    the criteria, then run the pure `fold` from `initial_state`. Returns the final state."""
    state = initial_state
    for event in events:
        if matches(event, event_types, aggregate_type, aggregate_id, from_ts, to_ts):
            state = fold(state, event)
    return state
