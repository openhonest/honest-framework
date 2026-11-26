# scenario: build_message rejects fields outside the chosen termination condition
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message rejects fields outside the chosen termination condition
"""Require a client fault and guidance for invalid termination fields."""

from honest_alerts import build_message
from laws_build_message import _REGISTERED, _given

_CASES = [
    ("ttl", None, None, None),
    ("ttl", 10, "system.ready", None),
    ("ttl", 10, None, {"ok": True}),
    ("event", None, None, None),
    ("event", 10, "system.ready", None),
    ("acknowledged", 10, None, None),
    ("acknowledged", None, "system.ready", None),
    ("acknowledged", None, None, {"ok": True}),
    ("never", 10, None, None),
    ("never", None, "system.ready", None),
    ("never", None, None, {"ok": True}),
    (None, None, None, None),
    ("unsupported", None, None, None),
]


def _offers_correction(message, condition):
    reads_as_clear = any(word in message for word in ("clear", "omit", "leave", "nothing", "unset"))
    reads_as_supply = any(word in message for word in ("set ", "supply", "specify", "provide", "choose"))
    optional_fields = all(field in message for field in ("ttl_seconds", "event_type", "event_filter"))
    if condition == "ttl":
        event_fields = "event fields" in message or all(field in message for field in ("event_type", "event_filter"))
        return "ttl_seconds" in message and event_fields and reads_as_supply and reads_as_clear
    if condition == "event":
        return optional_fields and "option" in message and reads_as_supply and reads_as_clear
    if condition in {"acknowledged", "never"}:
        clears_all = optional_fields or any(
            term in message for term in ("all optional fields", "all three fields", "all other fields")
        )
        return condition in message and clears_all and reads_as_clear
    names_supported = "supported" in message or all(
        name in message for name in ("ttl", "event", "acknowledged", "never")
    )
    return names_supported and reads_as_supply



def probe_build_message_termination_invalid_fields():
    failures = []
    for condition, ttl_seconds, event_type, event_filter in _CASES:
        termination = {
            "condition": condition,
            "ttl_seconds": ttl_seconds,
            "event_type": event_type,
            "event_filter": event_filter,
        }
        result = build_message(**_given("v1", _REGISTERED, termination))
        fault = (result.get("is_err"), result.get("code"), result.get("category"))
        message = result.get("message", "").casefold()
        problem = "field" in message and "condition" in message and any(
            word in message for word in ("match", "applicable", "requires", "invalid")
        )
        if condition not in {"ttl", "event", "acknowledged", "never"}:
            problem = "condition" in message and any(
                word in message for word in ("missing", "unsupported", "unknown", "invalid")
            )
        if fault != (True, "invalid_termination", "client") or not (
            problem and _offers_correction(message, condition)
        ):
            failures.append(f"expected invalid termination fault with corrective guidance for {termination!r}, got {result!r}")
    return failures
