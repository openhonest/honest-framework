# scenario: build_message accepts each well-formed termination condition
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message accepts each well-formed termination condition
"""Valid termination records are preserved through message construction."""

from honest_alerts import build_message
from laws_build_message import _REGISTERED, _given

_CASES = [
    ("ttl", 10, None, None),
    ("event", None, "system.ready", None),
    ("event", None, "system.ready", {"ok": True}),
    ("acknowledged", None, None, None),
    ("never", None, None, None),
]


def probe_build_message_termination_valid():
    failures = []
    for condition, ttl_seconds, event_type, event_filter in _CASES:
        termination = {
            "condition": condition,
            "ttl_seconds": ttl_seconds,
            "event_type": event_type,
            "event_filter": event_filter,
        }
        result = build_message(**_given("v1", _REGISTERED, termination))
        if result.get("is_err") is True or result.get("termination") != termination:
            failures.append(f"expected a Message preserving {termination!r}, got {result!r}")
    return failures
