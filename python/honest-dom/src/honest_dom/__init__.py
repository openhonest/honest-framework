"""honest-DOM server-side primitives.

The full DATAOS runtime lives in the browser as a small JS library (domx);
this Python package provides the types + beacon envelope builder + scoping
helpers so server code can type-check and emit DOM-related records.
"""
from honest_dom.core import (
    BeaconEnvelope,
    CachedRequest,
    Config,
    DomManifest,
    DomState,
    FetchResponse,
    MutationBatch,
    build_envelope,
    build_manifest,
    merge_state,
    scope_manifest,
    strip_values_for_production,
)

__all__ = [
    "BeaconEnvelope", "CachedRequest", "Config", "DomManifest",
    "DomState", "FetchResponse", "MutationBatch",
    "build_envelope", "build_manifest", "merge_state",
    "scope_manifest", "strip_values_for_production",
]
