# scenario: _is_dotted accepts only dotted names with nonempty components
# inherits: hd=python/honest-alerts/honest-alerts.hd::_is_dotted -> feature=specs/features/honest-alerts.feature::_is_dotted accepts only dotted names with nonempty components
"""Check the exact shape of a declared dotted registration name."""

from honest_alerts.pure import _is_dotted

_CASES = [
    ("approval.requested", True),
    ("a.b.c", True),
    ("A-1.b_2", True),
    ("", False),
    ("approval", False),
    (".", False),
    (".requested", False),
    ("approval.", False),
    ("approval..requested", False),
    (7, False),
]


def probe_is_dotted():
    failures = []
    for message_type, expected in _CASES:
        actual = _is_dotted(message_type)
        if actual is not expected:
            failures.append(f"_is_dotted({message_type!r}) returned {actual!r}, expected {expected!r}")
    return failures
