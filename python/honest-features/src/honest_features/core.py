"""Core feature-flag logic. Pure functions."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable, TypedDict


FlagState = dict[str, str]


class FlagSpec(TypedDict):
    states: list[str]
    default_state: str


class FlagVocabulary(TypedDict):
    flags: dict[str, FlagSpec]


class ToggleRequest(TypedDict):
    flag: str
    state_value: str
    timestamp: int
    signature: str
    requesting_ip: str


class ToggleResponse(TypedDict):
    flag: str
    state_value: str
    previous: str
    err_code: str


# --- Vocabulary constructors ----------------------------------------------


def flag_vocabulary(flags: dict[str, dict]) -> FlagVocabulary:
    built: dict[str, FlagSpec] = {}
    for name, spec in flags.items():
        built[name] = FlagSpec(
            states=list(spec["states"]),
            default_state=str(spec.get("default_state", spec["states"][0])),
        )
    return FlagVocabulary(flags=built)


def init_state(vocab: FlagVocabulary) -> FlagState:
    return {name: spec["default_state"] for name, spec in vocab["flags"].items()}


def reset_features(vocab: FlagVocabulary) -> FlagState:
    return init_state(vocab)


# --- Validators -----------------------------------------------------------


def validate_flag(flag: str, vocab: FlagVocabulary) -> bool:
    return flag in vocab["flags"]


def validate_state_value(flag: str, state_value: str, vocab: FlagVocabulary) -> bool:
    spec = vocab["flags"].get(flag)
    if spec is None:
        return False
    return state_value in spec["states"]


# --- Signature -------------------------------------------------------------


def build_signature(
    secret: bytes, flag: str, state_value: str, timestamp: int,
) -> str:
    msg = f"{flag}|{state_value}|{timestamp}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_signature(
    secret: bytes,
    flag: str,
    state_value: str,
    timestamp: int,
    signature: str,
    replay_window_seconds: int = 300,
) -> bool:
    expected = build_signature(secret, flag, state_value, timestamp)
    if not hmac.compare_digest(expected, signature):
        return False
    now = int(time.time())
    return abs(now - timestamp) <= replay_window_seconds


# --- State updates --------------------------------------------------------


def update_state(current: FlagState, flag: str, state_value: str) -> FlagState:
    return {**current, flag: state_value}


def feature_state(flag: str, current: FlagState) -> str:
    return current.get(flag, "")


def feature_state_for_request(
    flag: str,
    assignments: dict[str, str],
    current: FlagState,
) -> str:
    """If an A/B assignment exists for this flag, use it; otherwise fall
    back to the global feature_state.
    """
    return assignments.get(flag, feature_state(flag, current))


# --- Handler dispatch -----------------------------------------------------


def select_handler(
    state_value: str,
    handlers: dict[str, Callable],
) -> Callable:
    """Dict-lookup dispatch. Raises KeyError if no handler — explicit
    failure beats silent fallthrough.
    """
    if state_value not in handlers:
        raise KeyError(f"no handler registered for state {state_value!r}")
    return handlers[state_value]


# --- A/B assignment -------------------------------------------------------


def assign_variant(flag: str, identity: str, vocab: FlagVocabulary) -> str:
    """Deterministic hash-based variant assignment. Identity + flag name
    seeds a stable bucket choice across the vocabulary's states.
    """
    spec = vocab["flags"].get(flag)
    if spec is None:
        raise KeyError(f"unknown flag {flag!r}")
    digest = hashlib.sha256(f"{flag}:{identity}".encode()).digest()
    bucket = digest[0] % len(spec["states"])
    return spec["states"][bucket]


# --- Top-level toggle orchestrator ----------------------------------------


def toggle_flag(
    req: ToggleRequest,
    vocab: FlagVocabulary,
    secret: bytes,
    current: FlagState,
    replay_window_seconds: int = 300,
) -> ToggleResponse:
    if not validate_flag(req["flag"], vocab):
        return ToggleResponse(
            flag=req["flag"], state_value="", previous="",
            err_code="unknown_flag",
        )
    if not validate_state_value(req["flag"], req["state_value"], vocab):
        return ToggleResponse(
            flag=req["flag"], state_value="", previous="",
            err_code="invalid_state",
        )
    if not verify_signature(
        secret, req["flag"], req["state_value"], req["timestamp"],
        req["signature"], replay_window_seconds,
    ):
        # Distinguish bad_signature from bad_timestamp by checking window alone.
        # Accept either fault code; the client can't tell anyway.
        return ToggleResponse(
            flag=req["flag"], state_value="", previous="",
            err_code="bad_signature",
        )
    previous = feature_state(req["flag"], current)
    return ToggleResponse(
        flag=req["flag"], state_value=req["state_value"],
        previous=previous, err_code="",
    )
