"""Honest probe for honest-check's blocking_findings (Scenario: blocking_findings).

blocking_findings returns only the diagnostics whose severity reaches the blocking
threshold; it is pure. The scenario fixes the filter behaviour (an order-preserving
subset of the input, by severity against the threshold) but NOT the numeric encoding
of severity-to-int — what integer threshold corresponds to 'error', 'warning' or
'info'. This probe reads that encoding as the natural severity rank info<warning<error
(info=0, warning=1, error=2) with "reaches" meaning rank >= threshold, the convention
startup_check documents (severity 'error' blocks, warnings and infos do not). That
encoding is a GAP the scenario and .hd leave open; see the probe report.

Under that reading: threshold 2 keeps only errors, threshold 1 keeps errors and
warnings, threshold 0 keeps all three, and the empty input is the boundary. A
`return []` stub passes the empty case but fails the three non-empty cases; a
`return diagnostics` stub fails the threshold-2 and threshold-1 cases.
"""


def _diag(severity, rule_id):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": f"{rule_id} fired",
        "source_location": "case.py:1:1",
        "context": "",
        "fixable": False,
    }


_ERROR = _diag("error", "HC007")
_WARNING = _diag("warning", "HC003")
_INFO = _diag("info", "HC009")
_MIXED = [_ERROR, _WARNING, _INFO]

# Each case: the input diagnostics, the integer threshold, and the order-preserving
# subset blocking_findings must return under the natural severity rank.
_CASES = [
    {"diagnostics": _MIXED, "threshold": 2, "expect": [_ERROR]},
    {"diagnostics": _MIXED, "threshold": 1, "expect": [_ERROR, _WARNING]},
    {"diagnostics": _MIXED, "threshold": 0, "expect": [_ERROR, _WARNING, _INFO]},
    # Boundary: nothing to filter returns nothing.
    {"diagnostics": [], "threshold": 2, "expect": []},
]


def probe_blocking_findings():
    """blocking_findings returns the order-preserving subset of diagnostics reaching the threshold."""
    try:
        from honest_check import blocking_findings
    except ImportError as exc:
        return [f"cannot import blocking_findings: {exc}"]

    bad = []
    for case in _CASES:
        got = blocking_findings(case["diagnostics"], case["threshold"])
        if got != case["expect"]:
            bad.append(
                f"blocking_findings(severities="
                f"{[d['severity'] for d in case['diagnostics']]}, "
                f"threshold={case['threshold']}) -> "
                f"{[d['severity'] for d in got] if isinstance(got, list) else got!r}, "
                f"expected {[d['severity'] for d in case['expect']]}"
            )
    return bad
