# scenario: is_fault recognizes only records with the fault discriminator
# inherits: hd=python/honest-persist/honest-persist-pure.hd::is_fault -> feature=specs/features/honest-persist.feature::is_fault recognizes only records with the fault discriminator
from honest_persist import is_fault

_CASES = [
    (
        {
            "is_err": True,
            "code": "unknown_table",
            "message": "No such table",
            "detail": {"table": "missing"},
            "category": "refused",
            "results": [],
        },
        True,
    ),
    ({"table": "people"}, False),
    ([{"id": 1}], False),
    (1, False),
    (True, False),
    (None, False),
]


def probe_is_fault() -> list[str]:
    """Recognize a tagged fault among the declared Persist result shapes."""
    failures = []
    for value, expected in _CASES:
        actual = is_fault(value)
        if actual is not expected:
            failures.append(f"is_fault({value!r}) returned {actual!r}, expected {expected!r}")
    return failures
