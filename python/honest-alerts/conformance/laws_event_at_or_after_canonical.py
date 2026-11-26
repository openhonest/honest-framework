# scenario: event_at_or_after compares canonical Observe timestamps at microsecond precision
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::event_at_or_after -> feature=specs/features/honest-alerts.feature::event_at_or_after compares canonical Observe timestamps at microsecond precision
"""Compare canonical timestamps on either side of an integer second."""

_CASES = [
    ('1970-01-01T00:00:00.999999Z', 1, False),
    ('1970-01-01T00:00:01.000000Z', 1, True),
    ('1970-01-01T00:00:01.000001Z', 1, True),
    ('0001-01-01T00:00:00.000000Z', -62135596800, True),
    ('2000-02-29T23:59:59.000000Z', 951868799, True),
    ('2024-04-30T12:34:55.999999Z', 1714480496, False),
    ('2024-04-30T12:34:56.000000Z', 1714480496, True),
    ('9999-12-31T23:59:59.999999Z', 253402300799, True),
]


def probe_event_at_or_after_canonical():
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
