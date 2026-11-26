# scenario: uuid7_from_parts preserves the timestamp and entropy fields in canonical text
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::uuid7_from_parts -> feature=specs/features/honest-alerts.feature::uuid7_from_parts preserves the timestamp and entropy fields in canonical text
from honest_alerts.pure import uuid7_from_parts

_CASES = [
    (
        {"unix_ms": 1645557742000, "random_a": 3267, "random_b": 1784793296645077391},
        "017f22e2-79b0-7cc3-98c4-dc0c0c07398f",
    ),
    (
        {"unix_ms": 1645557742000, "random_a": 3266, "random_b": 1784793296645077391},
        "017f22e2-79b0-7cc2-98c4-dc0c0c07398f",
    ),
    (
        {"unix_ms": 1645557742000, "random_a": 64707, "random_b": 15619851351927241103},
        "017f22e2-79b0-7cc3-98c4-dc0c0c07398f",
    ),
]


def probe_uuid7_from_parts():
    """Return the canonical v7 text with declared fixed and supplied bits."""
    failures = []
    for given, expected in _CASES:
        actual = uuid7_from_parts(**given)
        if actual != expected:
            failures.append(f"uuid7_from_parts({given!r}) returned {actual!r}, expected {expected!r}")
    return failures
