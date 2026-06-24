"""Snapshot projections (section 6.3): replay a projection from a saved position, not the beginning.

For an aggregate with millions of events, folding the whole log on every read is too slow. A snapshot
records a projection's folded state at a log position; a later read starts from the snapshot and folds
only the events after it. Everything here is pure — building the record, deciding when a new snapshot is
due, declaring the projection, and resuming the fold. Persisting and loading the snapshot is the
boundary's concern (honest-persist), kept out of this module so observe stays a leaf above persist.

`resume_from_snapshot` treats `snapshot_at` as the position the snapshot already covers: an event whose
timestamp equals it is taken as already folded, so only strictly-later events are replayed. That is the
one rule that makes a snapshot exact rather than an approximation.
"""

from honest_observe.projections import matches


def build_snapshot(projection_id: str, snapshot_at: str, state: dict) -> dict:
    """A snapshot record (section 6.3): the projection it belongs to, the log position it covers, and
    the folded state at that position. Pure data."""
    return {"projection_id": projection_id, "snapshot_at": snapshot_at, "state": state}


def should_snapshot(events_since_snapshot: int, snapshot_interval) -> bool:
    """Whether a new snapshot is due (section 6.3): true once `events_since_snapshot` reaches a positive
    `snapshot_interval`. A `None` or non-positive interval means the projection is not snapshotted, so
    this is never true. Pure."""
    return snapshot_interval is not None and snapshot_interval > 0 and events_since_snapshot >= snapshot_interval


def declare_projection(projection_id, event_types, fold, initial_state, snapshot_interval=None, aggregate_type=None, aggregate_id=None) -> dict:
    """A declared projection (section 6.3): the id, filters, fold, initial state, and snapshot interval
    the boundary reads to maintain it. `snapshot_interval` is None when the projection is not
    snapshotted; the aggregate filters appear only when set. Pure data construction (it carries the
    fold function unchanged)."""
    declaration = {
        "projection_id": projection_id,
        "event_types": event_types,
        "fold": fold,
        "initial_state": initial_state,
        "snapshot_interval": snapshot_interval,
    }
    if aggregate_type is not None:
        declaration["aggregate_type"] = aggregate_type
    if aggregate_id is not None:
        declaration["aggregate_id"] = aggregate_id
    return declaration


def resume_from_snapshot(snapshot, events, fold, event_types=None, aggregate_type=None, aggregate_id=None, to_ts=None) -> dict:
    """Replay a projection from a snapshot (section 6.3): fold the events strictly after
    `snapshot["snapshot_at"]` that pass the filters onto `snapshot["state"]`, and return the resulting
    state. An event whose timestamp equals the snapshot position is already covered and is not re-folded.
    Pure: the events are data, the fold is pure, nothing is read from the log."""
    state = snapshot["state"]
    for event in events:
        if event["timestamp"] > snapshot["snapshot_at"] and matches(event, event_types, aggregate_type, aggregate_id, None, to_ts):
            state = fold(state, event)
    return state
