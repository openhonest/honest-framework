"""In-memory event log boundary — production replaces with honest-persist.

This is a single module-level list because the runtime state belongs at the
boundary. Tests use `reset_log()` to isolate.
"""
from __future__ import annotations

from honest_observe.events import reject_event
from honest_observe.types import EmitResult, Event, Rejection, Snapshot


_LOG: list[Event] = []
_REJECTIONS: list[Rejection] = []
_SNAPSHOTS: dict[str, Snapshot] = {}


def reset_log() -> None:
    """Test helper. Not called in production."""
    _LOG.clear()
    _REJECTIONS.clear()
    _SNAPSHOTS.clear()


# --- Output boundaries -----------------------------------------------------


def append_event(event: Event) -> EmitResult:
    _LOG.append(event)
    return EmitResult(event_id=event["event_id"], err_code="", err_category="")


def append_rejection(rej: Rejection) -> EmitResult:
    _REJECTIONS.append(rej)
    return EmitResult(event_id=rej["rejection_id"], err_code="", err_category="")


def write_snapshot(snap: Snapshot) -> None:
    _SNAPSHOTS[snap["projection_id"]] = snap


def export_otel(span: dict) -> None:
    """In M1 we just discard. Real implementation ships to an OTel collector."""
    return None


def stream_tail(event: Event) -> None:
    """Broadcast a newly appended event to subscribers. M1 stub."""
    return None


# --- Input boundaries ------------------------------------------------------


def read_event_log(
    from_ts: str,
    to_ts: str,
    filter_types: list[str] | None = None,
) -> list[Event]:
    filters = set(filter_types or [])
    out = []
    for ev in _LOG:
        if from_ts and ev["timestamp"] < from_ts:
            continue
        if to_ts and ev["timestamp"] > to_ts:
            continue
        if filters and ev["event_type"] not in filters:
            continue
        out.append(ev)
    return out


def read_snapshot(projection_id: str) -> Snapshot | None:
    return _SNAPSHOTS.get(projection_id)


def read_rejections() -> list[Rejection]:
    return list(_REJECTIONS)
