"""honest-observe IR. Keep in sync with honest-observe.hd."""
from __future__ import annotations

from typing import Any, Callable, TypedDict


class AuthPartition(TypedDict):
    caller_id: str
    caller_session: str
    data_owner_id: str
    factors_presented: list[str]
    request_signature: str


class EventMeta(TypedDict):
    environment: str
    tenant_id: str
    release: str
    correlation_id: str
    source: str
    source_hlc: str
    translator_version: str


class Event(TypedDict):
    event_id: str
    event_type: str
    event_version: str
    timestamp: str
    sequence: int
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    auth: AuthPartition
    meta: EventMeta


class EmitResult(TypedDict):
    event_id: str
    err_code: str
    err_category: str


class Snapshot(TypedDict):
    projection_id: str
    snapshot_at: str
    state_blob: dict[str, Any]


class Projection(TypedDict):
    projection_id: str
    event_types: list[str]
    fold_fn: Callable[[Snapshot, Event], Snapshot]
    initial_state: Snapshot
    snapshot_interval: int


class Rejection(TypedDict):
    rejection_id: str
    received_at: str
    source: str
    reason_code: str
    reason_detail: dict[str, Any]
    raw_event: dict[str, Any]
    translator_version: str


class HLC(TypedDict):
    physical: int
    logical: int
    source: str
