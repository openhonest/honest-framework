"""Orchestrators: emit a new event, run a projection."""
from __future__ import annotations

from typing import Any

from honest_observe.events import build_envelope, project
from honest_observe.log import append_event, read_event_log, write_snapshot
from honest_observe.types import EmitResult, Projection, Snapshot


def emit(
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> EmitResult:
    """Build the envelope and append in one shot. Returns EmitResult."""
    ev = build_envelope(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        context=context or {},
    )
    return append_event(ev)


def run_projection(
    proj: Projection,
    from_ts: str,
    to_ts: str,
) -> Snapshot:
    """Read events in range, fold via the projection's fold_fn, write snapshot."""
    events = read_event_log(from_ts, to_ts, proj["event_types"])
    final_state = project(events, proj["fold_fn"], proj["initial_state"])
    write_snapshot(final_state)
    return final_state
