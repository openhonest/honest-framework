"""prepare_report applies the adoption downgrade, the severity threshold and the
rule filters, then counts the survivors.

One enforced error-diagnostic at adoption Declared survives as an error: errors == 1,
total_count == 53. A diagnostic whose rule is above the declared level (HC-OR001 at
adoption Structural) is downgraded to info, so errors == 0.
"""


def _diag(rule_id, severity):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": "finding under test",
        "source_location": "src/x.py:10:1",
        "context": "class X:",
        "fixable": False,
    }


def _args(threshold):
    return {
        "paths": ["src/"],
        "format": "human",
        "severity": threshold,
        "include_rules": [],
        "exclude_rules": [],
        "config_path": "",
        "report_mode": False,
    }


# HC-P003 is enforced at every level, so at Declared the error survives (errors 1).
# HC-OR001 is a Declared-only rule, so at Structural it is downgraded to info
# (errors 0).
_CASES = [
    {
        "diagnostics": [_diag("HC-P003", "error")],
        "args": _args("error"),
        "adoption": "Declared",
        "expect": {"errors": 1, "total_count": 53},
    },
    {
        "diagnostics": [_diag("HC-OR001", "error")],
        "args": _args("info"),
        "adoption": "Structural",
        "expect": {"errors": 0},
    },
]


def probe_prepare_report():
    try:
        from honest_check import prepare_report
    except ImportError as exc:
        return [f"cannot import prepare_report: {exc}"]

    bad = []
    for case in _CASES:
        got = prepare_report(case["diagnostics"], case["args"], case["adoption"])
        for field, want in case["expect"].items():
            have = got.get(field) if isinstance(got, dict) else None
            if have != want:
                bad.append(
                    f"prepare_report(rule={case['diagnostics'][0]['rule_id']}, "
                    f"adoption={case['adoption']!r})[{field!r}] -> {have!r}, expected {want!r}"
                )
    return bad
