# scenario: refused builds a tagged fault with the supplied facts
# inherits: hd=python/honest-persist/honest-persist-pure.hd::refused -> feature=specs/features/honest-persist.feature::refused builds a tagged fault with the supplied facts
from honest_persist import refused

_CASES = [
    (
        {"code": "unknown_table", "message": "No such table", "detail": {"table": "missing"}},
        {
            "is_err": True,
            "code": "unknown_table",
            "message": "No such table",
            "detail": {"table": "missing"},
            "category": "refused",
            "results": [],
        },
    ),
]


def probe_refused() -> list[str]:
    """Preserve the supplied facts in the reserved tagged Fault."""
    failures = []
    for given, expected in _CASES:
        actual = refused(**given)
        if actual != expected:
            failures.append(f"refused({given!r}) returned {actual!r}, expected {expected!r}")
    return failures
