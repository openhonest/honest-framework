# scenario: add_display
# inherits: hd=python/honest-errors/honest-errors.hd::add_display -> feature=specs/features/honest-errors.feature::add_display

from copy import deepcopy

from honest_errors import NOTHING, add_display

_NOW = "2026-11-15T12:00:00Z"
_DUE = "2026-11-15T12:01:00Z"
_REPORT = {
    "exception_type": "ValueError",
    "message": "bad literal",
    "severity": "error",
    "environment": "development",
    "file": "svc.py",
    "line": 88,
    "function": "parse",
    "traceback": "Traceback ...",
    "context": {},
    "timestamp": _NOW,
}
_KEY = {"exception_type": "ValueError", "file": "svc.py", "line": 88}
_SHOWING = {"key": _KEY, "status": "showing", "until": NOTHING, "due": NOTHING}
_ONCE = {"kind": "once", "period": NOTHING}
_IMMEDIATE = {"kind": "immediate", "scheduled": NOTHING}

_CASES = [
    {
        "name": "absent display",
        "live": [_SHOWING],
        "display": NOTHING,
        "expect": {"state": {"live": [_SHOWING]}, "actions": []},
    },
    {
        "name": "already-live Once display",
        "live": [_SHOWING],
        "display": {"duration": _ONCE, "timing": _IMMEDIATE},
        "expect": {"state": {"live": [_SHOWING]}, "actions": []},
    },
    {
        "name": "scheduled display",
        "live": [],
        "display": {"duration": _ONCE, "timing": {"kind": "scheduled", "scheduled": {"at": _DUE}}},
        "expect": {
            "state": {"live": [{"key": _KEY, "status": "pending", "until": NOTHING, "due": _DUE}]},
            "actions": [],
        },
    },
    {
        "name": "immediate period display",
        "live": [],
        "display": {"duration": {"kind": "period", "period": {"seconds": 30}}, "timing": _IMMEDIATE},
        "expect": {
            "state": {
                "live": [{"key": _KEY, "status": "showing", "until": "2026-11-15T12:00:30Z", "due": NOTHING}],
            },
            "actions": [{"key": _KEY, "report": _REPORT, "kind": "show"}],
        },
    },
]


def probe_add_display():
    """Apply the declared cadence without changing the caller's live displays."""
    failures = []
    for case in _CASES:
        given = deepcopy({
            "state": {"live": case["live"]},
            "report": _REPORT,
            "cadence": {"respond": NOTHING, "display": case["display"]},
            "now": _NOW,
        })
        before = deepcopy(given)
        result = add_display(**given)
        if result != case["expect"]:
            failures.append(f'{case["name"]}: got {result!r}, expected {case["expect"]!r}')
        if given != before:
            failures.append(f'{case["name"]}: add_display changed its input')
    return failures
