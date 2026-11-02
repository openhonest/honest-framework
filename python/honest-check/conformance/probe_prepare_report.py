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


def _args(threshold, include_rules=None, exclude_rules=None, report_mode=False):
    return {
        "paths": ["src/"],
        "format": "human",
        "severity": threshold,
        "include_rules": include_rules or [],
        "exclude_rules": exclude_rules or [],
        "config_path": "",
        "report_mode": report_mode,
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
    # A warning below an --severity error threshold is dropped: the sole finding
    # does not survive, so every survivor count is 0.
    {
        "diagnostics": [_diag("HC-P001", "warning")],
        "args": _args("error"),
        "adoption": "Declared",
        "expect": {"errors": 0, "warnings": 0, "infos": 0},
    },
    # --rule HC-P003 keeps only HC-P003: the HC-P001 finding is filtered out, so the
    # survivor is the one error and warnings stays 0.
    {
        "diagnostics": [_diag("HC-P003", "error"), _diag("HC-P001", "warning")],
        "args": _args("info", include_rules=["HC-P003"]),
        "adoption": "Declared",
        "expect": {"errors": 1, "warnings": 0},
    },
    # --no-rule HC-P003 drops HC-P003: only the HC-P001 warning survives.
    {
        "diagnostics": [_diag("HC-P003", "error"), _diag("HC-P001", "warning")],
        "args": _args("info", exclude_rules=["HC-P003"]),
        "adoption": "Declared",
        "expect": {"errors": 0, "warnings": 1},
    },
    # --report mode tallies survivors per rule into rule_counts and carries the flag.
    {
        "diagnostics": [_diag("HC-P003", "error"), _diag("HC-P003", "error")],
        "args": _args("info", report_mode=True),
        "adoption": "Declared",
        "expect": {"rule_counts": {"HC-P003": 2}, "report_mode": True},
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
