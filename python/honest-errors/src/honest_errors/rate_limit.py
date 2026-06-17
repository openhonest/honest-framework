"""Rate limiter. Pure functions threading state dict — no class, no lock.

Concurrent callers must wrap `check_rate_limit` in their own lock if
thread-safety matters. Alternatively, the caller owns a single process-wide
state dict protected by a single lock.
"""
from __future__ import annotations

import time
from typing import Any, TypedDict

from honest_errors.types import ExceptionReport


class DedupKey(TypedDict):
    exception_type: str
    file: str
    line: int


class RateLimitConfig(TypedDict):
    dedup_window_seconds: int
    max_per_hour: int


class RateLimitDecision(TypedDict):
    should_send: bool
    reason: str


def dedup_key(report: ExceptionReport) -> DedupKey:
    return DedupKey(
        exception_type=report["exception_type"],
        file=report["file"],
        line=report["line"],
    )


def new_state() -> dict[str, Any]:
    """Fresh rate-limiter state. Caller owns the dict."""
    return {"dedup_cache": {}, "hourly_sends": []}


def check_rate_limit(
    key: DedupKey,
    config: RateLimitConfig,
    state: dict[str, Any],
    now: float | None = None,
) -> tuple[RateLimitDecision, dict[str, Any]]:
    """Pure. Return (decision, new_state). Caller persists new_state for the
    next call.
    """
    now = now or time.time()
    # Prune hourly_sends older than 1 hour.
    hour_ago = now - 3600
    hourly = [t for t in state.get("hourly_sends", []) if t > hour_ago]
    # Hourly cap.
    if len(hourly) >= config["max_per_hour"]:
        return (
            RateLimitDecision(
                should_send=False, reason="rate_limit_hourly",
            ),
            {**state, "hourly_sends": hourly},
        )
    # Dedup.
    cache = dict(state.get("dedup_cache", {}))
    key_tuple = (key["exception_type"], key["file"], key["line"])
    last_sent = cache.get(key_tuple)
    if last_sent is not None:
        if now - last_sent < config["dedup_window_seconds"]:
            return (
                RateLimitDecision(
                    should_send=False, reason="rate_limit_dedup",
                ),
                {**state, "hourly_sends": hourly, "dedup_cache": cache},
            )
    # Allow.
    cache[key_tuple] = now
    hourly = hourly + [now]
    # Prune old dedup entries (twice the window back).
    cutoff = now - config["dedup_window_seconds"] * 2
    cache = {k: v for k, v in cache.items() if v > cutoff}
    return (
        RateLimitDecision(should_send=True, reason=""),
        {"dedup_cache": cache, "hourly_sends": hourly},
    )
