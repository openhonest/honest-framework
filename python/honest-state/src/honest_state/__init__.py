"""honest-state — pure state machines + DATAOS manifest.

Server-side: transition(), validate_state(), validate_event() — all pure.
Client-side (collect/observe/apply) lives in honest-DOM; this module
defines the manifest shape and the transition primitives only.
"""
from honest_state.machine import (
    StateMachine,
    TransitionResult,
    advance,
    is_terminal,
    lookup_transition,
    state_machine,
    transition,
    validate_event,
    validate_state,
)
from honest_state.manifest import (
    ManifestEntry,
    StateManifest,
    manifest,
)

__all__ = [
    "ManifestEntry",
    "StateMachine",
    "StateManifest",
    "TransitionResult",
    "advance",
    "is_terminal",
    "lookup_transition",
    "manifest",
    "state_machine",
    "transition",
    "validate_event",
    "validate_state",
]
