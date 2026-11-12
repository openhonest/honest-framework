"""The rate-limiter (spec section 5). A pure, state-threaded throttle: no class, no lock, no module
global. The caller owns the state and threads it forward; now is an argument, never a clock read.
Suppression is returned as data (RateLimitDecision), never an exception or a silent drop.
"""


def dedup_key(report):
    """Project the throttle's identity out of a report (spec section 5): the exception_type, file and
    line that decide whether two failures are the same for deduplication."""
    return {
        "exception_type": report["exception_type"],
        "file": report["file"],
        "line": report["line"],
    }


def new_state():
    """Build the throttle's empty starting state (spec section 5): an empty dedup cache and an empty
    list of hourly sends, the seed the caller threads forward."""
    return {"dedup_cache": {}, "hourly_sends": []}


def check_rate_limit(key, config, state, now):
    """Decide whether a send may go out and return the decision together with the next state (spec
    section 5). Computes in order: prune hourly_sends older than one hour relative to now; if the
    hourly count is at max_per_hour, suppress rate_limit_hourly; if this key fired within
    dedup_window_seconds, suppress rate_limit_dedup; otherwise record the send, prune stale dedup
    entries, and allow with the empty reason. Returns a new State and never mutates the one given."""

    def _serialize(dedup):
        return f"{dedup['exception_type']}|{dedup['file']}|{dedup['line']}"

    one_hour = 3600
    window = config["dedup_window_seconds"]
    max_per_hour = config["max_per_hour"]
    serial = _serialize(key)
    pruned_hourly = [sent for sent in state["hourly_sends"] if now - sent < one_hour]

    if len(pruned_hourly) >= max_per_hour:
        next_state = {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": pruned_hourly}
        return ({"should_send": False, "reason": "rate_limit_hourly"}, next_state)

    if serial in state["dedup_cache"] and now - state["dedup_cache"][serial] < window:
        next_state = {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": pruned_hourly}
        return ({"should_send": False, "reason": "rate_limit_dedup"}, next_state)

    fresh_cache = {seen: fired for seen, fired in state["dedup_cache"].items() if now - fired < window}
    fresh_cache[serial] = now
    next_state = {"dedup_cache": fresh_cache, "hourly_sends": pruned_hourly + [now]}
    return ({"should_send": True, "reason": ""}, next_state)
