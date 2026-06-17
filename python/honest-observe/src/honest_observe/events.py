"""Event construction, projection, rejection. All pure."""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Callable

from honest_observe.types import (
    AuthPartition,
    Event,
    EventMeta,
    HLC,
    Projection,
    Rejection,
    Snapshot,
)


# --- Sub-envelope constructors --------------------------------------------


def extract_auth(context: dict[str, Any]) -> AuthPartition:
    a = context.get("auth", {}) or {}
    return AuthPartition(
        caller_id=str(a.get("caller_id", "")),
        caller_session=str(a.get("caller_session", "")),
        data_owner_id=str(a.get("data_owner_id", "")),
        factors_presented=list(a.get("factors_presented", [])),
        request_signature=str(a.get("request_signature", "")),
    )


def extract_meta(context: dict[str, Any]) -> EventMeta:
    m = context.get("meta", {}) or {}
    return EventMeta(
        environment=str(m.get("environment", "dev")),
        tenant_id=str(m.get("tenant_id", "")),
        release=str(m.get("release", "0.0.0")),
        correlation_id=str(m.get("correlation_id", "")),
        source=str(m.get("source", "framework")),
        source_hlc=str(m.get("source_hlc", "")),
        translator_version=str(m.get("translator_version", "")),
    )


def next_sequence(aggregate_id: str) -> int:
    """Deterministic (within a session) monotonic sequence keyed by aggregate.
    In production, this would consult the database; here we use a process-local
    counter, which is adequate for unit tests. Honest-code note: this IS state,
    so in production it moves behind a proper boundary_in.
    """
    _SEQUENCES[aggregate_id] = _SEQUENCES.get(aggregate_id, 0) + 1
    return _SEQUENCES[aggregate_id]


_SEQUENCES: dict[str, int] = {}


def advance_hlc(local: HLC, incoming: HLC) -> HLC:
    """Hybrid-Logical-Clock merge: max(physical) with logical tie-break."""
    now_ms = int(time.time() * 1000)
    physical = max(local["physical"], incoming["physical"], now_ms)
    if physical == local["physical"] == incoming["physical"]:
        logical = max(local["logical"], incoming["logical"]) + 1
    elif physical == local["physical"]:
        logical = local["logical"] + 1
    elif physical == incoming["physical"]:
        logical = incoming["logical"] + 1
    else:
        logical = 0
    return HLC(physical=physical, logical=logical, source=local["source"])


# --- Envelope builder ------------------------------------------------------


def build_envelope(
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> Event:
    seq = next_sequence(aggregate_id)
    ts = context.get("timestamp") or _iso_now()
    return Event(
        event_id=_event_id(event_type, aggregate_id, seq, ts),
        event_type=event_type,
        event_version=str(context.get("event_version", "1")),
        timestamp=ts,
        sequence=seq,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=dict(payload),
        auth=extract_auth(context),
        meta=extract_meta(context),
    )


def _event_id(event_type: str, agg_id: str, seq: int, ts: str) -> str:
    h = hashlib.sha256(f"{event_type}:{agg_id}:{seq}:{ts}".encode()).hexdigest()
    return h[:24]


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- Projections -----------------------------------------------------------


def fold(state: Snapshot, event: Event) -> Snapshot:
    """Default fold: carry state forward; specific projections replace this."""
    return state


def project(
    events: list[Event],
    fold_fn: Callable[[Snapshot, Event], Snapshot],
    initial_state: Snapshot,
) -> Snapshot:
    """Pure reduce over events."""
    state = initial_state
    for ev in events:
        state = fold_fn(state, ev)
    return state


# --- Rejections ------------------------------------------------------------


def reject_event(reason_code: str, raw: dict[str, Any]) -> Rejection:
    return Rejection(
        rejection_id=str(uuid.uuid4()),
        received_at=_iso_now(),
        source=str(raw.get("_source", "unknown")),
        reason_code=reason_code,
        reason_detail=dict(raw.get("_detail", {})),
        raw_event=dict(raw),
        translator_version=str(raw.get("_translator_version", "")),
    )


# --- External translators --------------------------------------------------


def recognize_stripe_payment(raw: dict[str, Any]) -> bool:
    return raw.get("type") == "payment_intent.succeeded"


def translate_stripe_payment(raw: dict[str, Any]) -> Event:
    data = raw.get("data", {}).get("object", {})
    aggregate_id = str(data.get("id", raw.get("id", "unknown")))
    amount = data.get("amount", 0)
    currency = data.get("currency", "usd")
    return build_envelope(
        event_type="order.paid",
        aggregate_type="order",
        aggregate_id=aggregate_id,
        payload={"amount": amount, "currency": currency, "provider": "stripe"},
        context={"meta": {"source": "stripe", "translator_version": "1"}},
    )


def translate_generic_webhook(source_id: str, raw: dict[str, Any]) -> Event:
    return build_envelope(
        event_type=f"webhook.{source_id}",
        aggregate_type="webhook",
        aggregate_id=str(raw.get("id", _event_id(source_id, "wh", 0, _iso_now()))),
        payload=dict(raw),
        context={"meta": {"source": source_id, "translator_version": "1"}},
    )


def resolve_identity(
    external_id: str,
    source: str,
    bindings: dict[str, str],
) -> str:
    """Lookup external id → internal id. Raises KeyError if unknown."""
    key = f"{source}:{external_id}"
    if key not in bindings:
        raise KeyError(f"identity_unknown: {key}")
    return bindings[key]


# --- OTel mapping ---------------------------------------------------------


def map_event_to_otel(event: Event) -> dict[str, Any]:
    """Map a framework Event into an OTel span dict."""
    return {
        "trace_id": event["meta"]["correlation_id"] or event["event_id"],
        "span_id": event["event_id"],
        "name": event["event_type"],
        "start_time": event["timestamp"],
        "attributes": {
            "hf.aggregate_type": event["aggregate_type"],
            "hf.aggregate_id": event["aggregate_id"],
            "hf.sequence": event["sequence"],
        },
    }
