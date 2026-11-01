"""resolve_exit_code decides the process exit code from the prepared report.

errors > 0 with report_mode False is 1; no error is 0; report_mode True with errors
is 0, because --report reports and does not judge. The code is compared through int()
because ExitCode is the '0'/'1'/'2' vocabulary.
"""


def _report(errors, report_mode):
    return {
        "diagnostics": [],
        "errors": errors,
        "warnings": 0,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 50,
        "total_count": 50,
        "report_mode": report_mode,
    }


_CASES = [
    {"report": _report(1, False), "expect": 1},
    {"report": _report(0, False), "expect": 0},
    {"report": _report(2, True), "expect": 0},
]


def probe_resolve_exit_code():
    try:
        from honest_check import resolve_exit_code
    except ImportError as exc:
        return [f"cannot import resolve_exit_code: {exc}"]

    bad = []
    for case in _CASES:
        got = resolve_exit_code(case["report"])
        try:
            code = int(got)
        except (ValueError, TypeError):
            bad.append(
                f"resolve_exit_code(errors={case['report']['errors']}, "
                f"report_mode={case['report']['report_mode']}) -> {got!r}, "
                f"not an exit code; expected {case['expect']}"
            )
            continue
        if code != case["expect"]:
            bad.append(
                f"resolve_exit_code(errors={case['report']['errors']}, "
                f"report_mode={case['report']['report_mode']}) -> {code}, "
                f"expected {case['expect']}"
            )
    return bad
