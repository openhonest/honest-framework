"""Honest probe for honest-check's format_human (feature Scenario: format_human).

format_human renders the human-readable CLI default from a prepared CheckReport: the
adoption line, then one block per diagnostic (a 'file:line:col: severity rule_id' header
split from source_location, the message, the quoted context), closing with the
'Found N errors, M warnings.' tally; under report_mode it renders the per-rule table from
rule_counts instead. It returns the finished text and does no I/O.

Each case pins the literal text the scenario and the .hd note fix: the adoption-line
phrases, the exact header line for a given diagnostic, the message, and the tally line
with the report's error and warning counts plugged in. A stub returning "" fails the tally
and header checks. The whitespace between blocks is not fixed, so the probe asserts
containment of the fixed fragments, not an exact whole-string match.
"""


def _diag(rule_id, severity, message, source_location, context="", fixable=False):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": source_location,
        "context": context,
        "fixable": fixable,
    }


def _report(diagnostics, errors, warnings, infos, adoption, enforced_count,
            total_count, rule_counts=None, report_mode=False):
    return {
        "diagnostics": diagnostics,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "rule_counts": rule_counts or {},
        "adoption": adoption,
        "enforced_count": enforced_count,
        "total_count": total_count,
        "report_mode": report_mode,
    }


# Each case: the CheckReport to render, and the fixed text fragments the output must carry.
_CASES = [
    # One error finding: adoption line, the header split from source_location, the message,
    # and the 'Found 1 errors, 0 warnings.' tally.
    {
        "report": _report(
            [_diag("HC-P001", "error", "msg one", "src/x.py:10:5", "if a:")],
            errors=1, warnings=0, infos=0,
            adoption="Declared", enforced_count=58, total_count=58,
        ),
        "contains": [
            "adoption level Declared",
            "58 of 58 rules enforced.",
            "src/x.py:10:5: error HC-P001",
            "msg one",
            "Found 1 errors, 0 warnings.",
        ],
    },
    # The tally reads the report's own counts, not the diagnostic list length.
    {
        "report": _report(
            [
                _diag("HC-P001", "error", "a", "src/x.py:1:1"),
                _diag("HC-P004", "warning", "b", "src/y.py:2:1"),
            ],
            errors=2, warnings=1, infos=0,
            adoption="Declared", enforced_count=58, total_count=58,
        ),
        "contains": ["Found 2 errors, 1 warnings."],
    },
    # Under report_mode the per-rule table from rule_counts is rendered: the rule and its count.
    {
        "report": _report(
            [],
            errors=3, warnings=0, infos=0,
            adoption="Declared", enforced_count=58, total_count=58,
            rule_counts={"HC-P001": 3}, report_mode=True,
        ),
        "contains": ["HC-P001", "3"],
    },
]


def probe_format_human():
    """format_human renders the adoption line, the per-finding blocks and the tally."""
    try:
        from honest_check import format_human
    except ImportError as exc:
        return [f"cannot import format_human: {exc}"]

    bad = []
    for case in _CASES:
        try:
            got = format_human(report=case["report"])
        except Exception as exc:
            bad.append(f"format_human raised {exc!r}")
            continue
        for fragment in case["contains"]:
            if fragment not in got:
                bad.append(
                    f"format_human output missing {fragment!r}; got {got!r}"
                )
    return bad
