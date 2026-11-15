"""Honest probe for honest-check's prepare_report (feature Scenario: prepare_report).

prepare_report turns the raw per-file findings into the CheckReport the formatters
render. It applies, in order: the adoption downgrade (a diagnostic whose rule is not
enforced at the declared level becomes info), the --severity threshold (findings below
it are dropped), and the --rule/--no-rule filters; then it counts the survivors into
errors/warnings/infos, fills rule_counts only under --report, and records adoption,
enforced_count and total_count (58).

Each case states a diagnostic list, the CliArgs, and the adoption level, and pins the
CheckReport fields the scenario fixes. The counts move with the downgrade, the threshold
and the filters, so a stub returning an empty report (every count 0, rule_counts {}) fails
every non-absence case. The membership the downgrade reads (HC-P004 unenforced at
Structural, HC-P001 enforced) and the enforced_count numbers (58 at Declared, 11 at
Structural) are the .hd's declared adoption-level sets, not recomputed here.
"""


def _args(severity="info", include=None, exclude=None, report_mode=False):
    return {
        "paths": [],
        "format": "human",
        "severity": severity,
        "include_rules": include or [],
        "exclude_rules": exclude or [],
        "config_path": "",
        "report_mode": report_mode,
        "declaration": "",
        "exports": "",
    }


def _diag(rule_id, severity):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": "m",
        "source_location": "a.py:1:1",
        "context": "",
        "fixable": False,
    }


_D_ERR = _diag("HC-P001", "error")
_D_WARN = _diag("HC-P004", "warning")
_D_INFO = _diag("HC003", "info")
_D_P004_ERR = _diag("HC-P004", "error")

# Each case: the inputs prepare_report takes, and the CheckReport fields the scenario fixes.
_CASES = [
    # Keep every finding (threshold 'info'), Declared enforces all 58 so nothing downgrades.
    {
        "diagnostics": [_D_ERR, _D_WARN, _D_INFO],
        "args": _args(severity="info"),
        "adoption": "Declared",
        "expect": {
            "errors": 1,
            "warnings": 1,
            "infos": 1,
            "rule_counts": {},
            "adoption": "Declared",
            "enforced_count": 58,
            "total_count": 58,
            "report_mode": False,
        },
    },
    # Adoption downgrade: Structural enforces HC-P001 but not HC-P004, so the HC-P004
    # error is downgraded to info while the HC-P001 error stands. Threshold 'info' keeps both.
    {
        "diagnostics": [_D_P004_ERR, _diag("HC-P001", "error")],
        "args": _args(severity="info"),
        "adoption": "Structural",
        "expect": {
            "errors": 1,
            "warnings": 0,
            "infos": 1,
            "adoption": "Structural",
            "enforced_count": 11,
            "total_count": 58,
        },
    },
    # Severity threshold 'error' drops the warning and the info, keeping only the error.
    {
        "diagnostics": [_D_ERR, _D_WARN, _D_INFO],
        "args": _args(severity="error"),
        "adoption": "Declared",
        "expect": {"errors": 1, "warnings": 0, "infos": 0},
    },
    # --rule include filter keeps only HC-P001; the HC-P004 error is filtered out.
    {
        "diagnostics": [_D_ERR, _D_P004_ERR],
        "args": _args(severity="info", include=["HC-P001"]),
        "adoption": "Declared",
        "expect": {"errors": 1, "warnings": 0, "infos": 0},
    },
    # --no-rule exclude filter drops HC-P004, keeping HC-P001.
    {
        "diagnostics": [_D_ERR, _D_P004_ERR],
        "args": _args(severity="info", exclude=["HC-P004"]),
        "adoption": "Declared",
        "expect": {"errors": 1, "warnings": 0, "infos": 0},
    },
    # --report fills rule_counts with each rule's finding count; empty otherwise.
    {
        "diagnostics": [_D_ERR, _D_ERR, _D_P004_ERR],
        "args": _args(severity="info", report_mode=True),
        "adoption": "Declared",
        "expect": {
            "errors": 3,
            "rule_counts": {"HC-P001": 2, "HC-P004": 1},
            "report_mode": True,
        },
    },
]


def probe_prepare_report():
    """prepare_report applies the downgrade, threshold and filters, then counts the survivors."""
    try:
        from honest_check import prepare_report
    except ImportError as exc:
        return [f"cannot import prepare_report: {exc}"]

    bad = []
    for case in _CASES:
        try:
            got = prepare_report(
                diagnostics=case["diagnostics"],
                args=case["args"],
                adoption=case["adoption"],
            )
        except Exception as exc:
            bad.append(f"prepare_report({case['adoption']}) raised {exc!r}")
            continue
        for field, want in case["expect"].items():
            have = got.get(field) if hasattr(got, "get") else None
            if have != want:
                bad.append(
                    f"prepare_report({case['adoption']}, {case['args']['severity']}) "
                    f".{field} -> {have!r}, expected {want!r}"
                )
    return bad
