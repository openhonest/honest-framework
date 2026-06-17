"""honest-features — HMAC-signed feature flags with handler dispatch.

Flags declared as a vocabulary. HMAC(secret, flag|state|ts) signs toggles.
Replay window enforced. Handler table dispatched by current state.
"""
from honest_features.core import (
    FlagSpec,
    FlagState,
    FlagVocabulary,
    ToggleRequest,
    ToggleResponse,
    assign_variant,
    build_signature,
    feature_state,
    feature_state_for_request,
    flag_vocabulary,
    init_state,
    reset_features,
    select_handler,
    toggle_flag,
    update_state,
    validate_flag,
    validate_state_value,
    verify_signature,
)

__all__ = [
    "FlagSpec",
    "FlagState",
    "FlagVocabulary",
    "ToggleRequest",
    "ToggleResponse",
    "assign_variant",
    "build_signature",
    "feature_state",
    "feature_state_for_request",
    "flag_vocabulary",
    "init_state",
    "reset_features",
    "select_handler",
    "toggle_flag",
    "update_state",
    "validate_flag",
    "validate_state_value",
    "verify_signature",
]
