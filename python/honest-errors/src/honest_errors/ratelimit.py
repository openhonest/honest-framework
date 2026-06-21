"""The rate-limiter (section 5): a pure, state-threaded throttle.

No class, no lock, no module-global state. The caller owns the state dict and threads it forward;
`check_rate_limit` returns `(decision, new_state)` and never mutates its argument. `now` is an
argument, not a clock read. Suppression is returned data (a RateLimitDecision with a reason from
SUPPRESS_REASONS), never an exception or a silent drop — so honest-test can enumerate every
suppression path.
"""

_SECONDS_PER_HOUR = 3600


def dedup_key(report):
    """The throttle's identity for a report (section 5): exception_type, file, line. Pure."""
    return {"exception_type": report["exception_type"], "file": report["file"], "line": report["line"]}


def new_state():
    """A fresh, empty rate-limit state (section 5): no dedup entries, no recorded sends."""
    return {"dedup_cache": {}, "hourly_sends": []}


def _key_str(key):
    return f"{key['exception_type']}|{key['file']}|{key['line']}"


def check_rate_limit(key, config, state, now):
    """Decide whether a send is allowed, threading state forward (section 5). Pure: returns
    (RateLimitDecision, new_state) and never mutates `state`.

    1. Prune hourly sends older than one hour relative to `now`.
    2. At max_per_hour -> suppress (rate_limit_hourly).
    3. Fired within dedup_window_seconds -> suppress (rate_limit_dedup).
    4. Otherwise record the send, prune stale dedup entries, allow.
    """
    recent_sends = [sent for sent in state["hourly_sends"] if now - sent < _SECONDS_PER_HOUR]
    if len(recent_sends) >= config["max_per_hour"]:
        return {"should_send": False, "reason": "rate_limit_hourly"}, {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": recent_sends}
    name = _key_str(key)
    last_sent = state["dedup_cache"].get(name)
    if last_sent is not None and now - last_sent < config["dedup_window_seconds"]:
        return {"should_send": False, "reason": "rate_limit_dedup"}, {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": recent_sends}
    fresh_cache = {entry: sent for entry, sent in state["dedup_cache"].items() if now - sent < config["dedup_window_seconds"]}
    fresh_cache[name] = now
    return {"should_send": True, "reason": ""}, {"dedup_cache": fresh_cache, "hourly_sends": recent_sends + [now]}
