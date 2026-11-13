"""The rate-limiter (architecture section 5).

A pure, state-threaded throttle: no class, no lock, no module-global state. The caller owns the state
and threads it forward. check_rate_limit takes now as an argument, returns a RateLimitOutcome holding
the decision and a new state, reports suppression as data, and never mutates its state argument.
"""

_ONE_HOUR_SECONDS = 3600


def dedup_key(report):
    """Build the de-duplication identity of a report (section 5): a DedupKey carrying the report's
    exception_type, file and line. Two reports with the same three values are the same failure."""
    return {
        "exception_type": report["exception_type"],
        "file": report["file"],
        "line": report["line"],
    }


def new_state():
    """A fresh, empty throttle state (section 5): empty dedup_cache, empty hourly_sends. The host calls
    this once to seed the state it then threads through capture."""
    return {"dedup_cache": {}, "hourly_sends": []}


def check_rate_limit(key, config, state, now):
    """The pure, state-threaded throttle (section 5). It (1) prunes hourly_sends older than one hour
    relative to now; (2) if the hourly count is at max_per_hour, suppresses with reason
    'rate_limit_hourly'; (3) else if this key fired within dedup_window_seconds, suppresses with reason
    'rate_limit_dedup'; (4) otherwise records the send, prunes stale dedup entries, and allows with
    reason None. It returns a RateLimitOutcome and never mutates its state argument."""
    serialized = "|".join([key["exception_type"], key["file"], str(key["line"])])
    recent = [sent for sent in state["hourly_sends"] if now - sent <= _ONE_HOUR_SECONDS]
    if len(recent) >= config["max_per_hour"]:
        return {
            "decision": {"should_send": False, "reason": "rate_limit_hourly"},
            "next_state": {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": recent},
        }
    last_fired = state["dedup_cache"].get(serialized)
    if last_fired is not None and now - last_fired < config["dedup_window_seconds"]:
        return {
            "decision": {"should_send": False, "reason": "rate_limit_dedup"},
            "next_state": {"dedup_cache": dict(state["dedup_cache"]), "hourly_sends": recent},
        }
    fresh_cache = {
        serial: fired
        for serial, fired in state["dedup_cache"].items()
        if now - fired < config["dedup_window_seconds"]
    }
    fresh_cache[serialized] = now
    return {
        "decision": {"should_send": True, "reason": None},
        "next_state": {"dedup_cache": fresh_cache, "hourly_sends": recent + [now]},
    }
