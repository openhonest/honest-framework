# scenario: is_terminated skips a malformed timestamp and matches a later Observe event
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::is_terminated -> feature=specs/features/honest-alerts.feature::is_terminated skips a malformed timestamp and matches a later Observe event
"""Event termination skips an invalid record and still reads the next Observe event."""

from honest_alerts import is_terminated
from honest_observe import build_event

from laws_is_terminated import _RECIP, _message, _termination

_TIMESTAMP = "1970-01-01T00:00:01.000001Z"
_MESSAGE = _message(
    "0192f000-0000-7000-8000-000000000001",
    _RECIP,
    1,
    _termination("event", None, "system.ready", None),
    "actor",
)


def probe_is_terminated_observe_timestamp():
    matching = build_event(
        event_type="system.ready",
        event_version="1",
        aggregate_type="system",
        aggregate_id="system-1",
        payload={"ready": True},
        auth={},
        meta={},
        event_id="0192f000-0000-7000-8000-000000000002",
        timestamp=_TIMESTAMP,
        sequence=1,
    )
    if matching.get("is_err") or matching.get("timestamp") != _TIMESTAMP:
        return [f"Observe did not produce the expected event timestamp: {matching!r}"]

    malformed = {**matching, "timestamp": "not a timestamp"}
    failures = []
    for events, expected in (([malformed, matching], True), ([malformed], False)):
        try:
            actual = is_terminated(_MESSAGE, _RECIP, 2, events, None)
        except TypeError as exc:
            failures.append(f"is_terminated raised on {len(events)} Observe event(s): {exc}")
            continue
        if actual is not expected:
            failures.append(f"is_terminated with {len(events)} Observe event(s) returned {actual!r}, expected {expected!r}")
    return failures
