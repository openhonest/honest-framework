"""Projections: the event-type filter predicate, the pure fold over a filtered slice, the projection
handle builder, the snapshot builder and the resume-from-snapshot fold (honest-observe.hd, section
6).

matches is the one place the event-type filter is decided, so apply_projection and resume_from_snapshot
fold over exactly the events a projection asked for and no others. The filter lives in the Projection
handle: apply_projection and resume_from_snapshot read projection["event_types"] rather than take a
duplicate argument beside it. The filtered slice is reduced with the caller's pure accumulator through
functools.reduce over a filter, so no imperative loop or branch decides the fold (P01). All five are
pure: no I/O, no mutation, so a projection cannot drift from the log.
"""

from functools import reduce

from honest_observe.types import Projection


def matches(event, event_types):
    """The projection filter predicate: true when the event's type is one of the requested types
    (section 6.1). Pure: a membership test, no world, no fault."""
    return event["event_type"] in event_types


def apply_projection(projection, events, fold, initial_state):
    """Run a projection: read the handle's event_types, keep only the events matches passes, then fold
    the kept events in order into a derived read model with the caller's pure accumulator (section
    6.1). fold is the pure (state, event) -> state function, initial_state its seed. No I/O and no
    mutation: the fold returns new state each step."""
    event_types = projection["event_types"]
    kept = filter(lambda event: matches(event, event_types), events)
    return reduce(fold, kept, initial_state)


def declare_projection(projection_id, event_types, fold, initial_state):
    """Declare a named projection, returning the flat Projection handle registered under projection_id
    over the given event types (section 6). fold and initial_state are named here and passed to
    apply_projection at run time, so they are not stored in the serializable handle. Pure: it builds a
    record, reads no world and returns no fault."""
    return {"projection_id": projection_id, "event_types": event_types}


def build_snapshot(projection_id, snapshot_at, state):
    """Build a projection snapshot: package projection_id, the log position snapshot_at it covers, and
    the folded state at that position into a snapshot record, so a projection over millions of events
    need not replay from the beginning every time (section 6.3). Pure: no world, no fault."""
    return {"projection_id": projection_id, "snapshot_at": snapshot_at, "state": state}


def resume_from_snapshot(projection, snapshot, events, fold):
    """Resume a projection from a snapshot: read the handle's event_types, keep only the matching
    events in the log tail, and fold them onto the snapshot's prior state with the same pure
    accumulator (section 6.3). The resumed state equals a full replay, so a snapshot is an optimization
    that cannot change the answer. Pure: no I/O, no mutation."""
    event_types = projection["event_types"]
    kept = filter(lambda event: matches(event, event_types), events)
    return reduce(fold, kept, snapshot["state"])
