"""DATAOS manifest shape."""
from __future__ import annotations

from typing import TypedDict


class ManifestEntry(TypedDict):
    selector: str
    read: str
    write: str


class StateManifest(TypedDict):
    entries: dict[str, ManifestEntry]


def manifest(entries: dict[str, dict]) -> StateManifest:
    built: dict[str, ManifestEntry] = {}
    for name, spec in entries.items():
        built[name] = ManifestEntry(
            selector=str(spec.get("selector", "")),
            read=str(spec.get("read", "value")),
            write=str(spec.get("write", "value")),
        )
    return StateManifest(entries=built)
