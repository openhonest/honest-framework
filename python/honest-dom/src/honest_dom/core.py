from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict


class Config(TypedDict):
    selector: str
    read: str
    write: str
    watch: str


class DomManifest(TypedDict):
    entries: dict[str, Config]


class DomState(TypedDict):
    values: dict[str, Any]


class MutationBatch(TypedDict):
    records: list[Any]
    frame_id: int


class CachedRequest(TypedDict):
    url: str
    state: DomState
    timestamp: int


class BeaconEnvelope(TypedDict):
    event_id: str
    event_type: str
    event_version: str
    timestamp: str
    source: str
    session_id: str
    request_id: str
    payload: dict[str, Any]


class FetchResponse(TypedDict):
    status: int
    body: str
    request_id: str


# --- Constructors / transforms -------------------------------------------


def build_manifest(entries: dict[str, dict]) -> DomManifest:
    """Pure. Wrap a plain dict of selectors into a DomManifest."""
    built: dict[str, Config] = {}
    for slot, spec in entries.items():
        built[slot] = Config(
            selector=str(spec["selector"]),
            read=str(spec.get("read", "value")),
            write=str(spec.get("write", "value")),
            watch=str(spec.get("watch", "input")),
        )
    return DomManifest(entries=built)


def merge_state(a: DomState, b: DomState) -> DomState:
    return DomState(values={**a["values"], **b["values"]})


def scope_manifest(root: DomManifest, subtree: DomManifest) -> DomManifest:
    """Intersection of two manifests by key. Used for component-scoped reads."""
    intersection = {
        k: root["entries"][k]
        for k in subtree["entries"]
        if k in root["entries"]
    }
    return DomManifest(entries=intersection)


def build_envelope(
    event_type: str,
    payload: dict[str, Any],
    request_id: str,
    session_id: str,
) -> BeaconEnvelope:
    return BeaconEnvelope(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        event_version="1",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        source="browser",
        session_id=session_id,
        request_id=request_id,
        payload=dict(payload),
    )


def strip_values_for_production(envelope: BeaconEnvelope) -> BeaconEnvelope:
    """Remove PII / free-text values from the payload; keep only keys."""
    safe_payload = {k: f"<{type(v).__name__}>" for k, v in envelope["payload"].items()}
    return BeaconEnvelope(**{**envelope, "payload": safe_payload})
