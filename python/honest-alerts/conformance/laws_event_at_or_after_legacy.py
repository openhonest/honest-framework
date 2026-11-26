# scenario: event_at_or_after accepts legacy integers and rejects unsupported timestamps
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::event_at_or_after -> feature=specs/features/honest-alerts.feature::event_at_or_after accepts legacy integers and rejects unsupported timestamps
"""Preserve epoch-second integers while rejecting missing and unsupported timestamps."""

_CASES = [
    (-1, 0, False),
    (0, 0, True),
    (1, 0, True),
    (True, 0, False),
    (False, 0, False),
    (None, 0, False),
    ('not a timestamp', 0, False),
    ('0000-12-31T23:59:59.999999Z', -62135596801, False),
    ('2001-02-29T23:59:59.999999Z', 983318400, False),
]


def probe_event_at_or_after_legacy():
    try:
        from honest_alerts.pure import event_at_or_after
    except ImportError as exc:
        return [f"cannot import event_at_or_after: {exc}"]

    failures = []
    for timestamp, sent_at, expected in _CASES:
        actual = event_at_or_after(timestamp, sent_at)
        if actual is not expected:
            failures.append(f"event_at_or_after({timestamp!r}, {sent_at}) returned {actual!r}, expected {expected!r}")
    return failures
