"""format_github renders GitHub Actions workflow-command annotations: a leading
'::notice::' line carrying the adoption line, then one '::error' or '::warning' line
per finding.

Each finding names its split file, line and col and its rule title and message. An
error finding takes the '::error' command, a warning finding the '::warning' command.
A three-colon location splits from the right into file, line and col.
"""


def _diag(source_location, rule_id="HC-P003", severity="error"):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": "class declaration",
        "source_location": source_location,
        "context": "class X:",
        "fixable": False,
    }


def _report(diag, errors=1, warnings=0):
    return {
        "diagnostics": [diag],
        "errors": errors,
        "warnings": warnings,
        "infos": 0,
        "rule_counts": {},
        "adoption": "Declared",
        "enforced_count": 50,
        "total_count": 50,
        "report_mode": False,
    }


def probe_format_github():
    try:
        from honest_check import format_github
        from honest_check.report import by_format
    except ImportError as exc:
        return [f"cannot import format_github: {exc}"]

    bad = []
    got = format_github(_report(_diag("src/x.py:10:1")))
    if not isinstance(got, str):
        return [f"format_github(report) -> {got!r}, expected a string"]

    # The leading notice line carries both halves of the adoption line.
    if "::notice::honest-check: adoption level Declared" not in got:
        bad.append(f"format_github is missing the '::notice::' adoption line; got {got!r}")
    if "50 of 50 rules enforced." not in got:
        bad.append(f"format_github is missing the enforced-count phrase; got {got!r}")

    # The error line names the split file/line/col and the rule title and message, and
    # sits on its own line after the notice line, so the newline join is exercised too.
    if "\n::error file=src/x.py,line=10,col=1," not in got:
        bad.append(f"format_github did not render the split error location; got {got!r}")
    if "title=HC-P003::class declaration" not in got:
        bad.append(f"format_github did not render the rule title and message; got {got!r}")

    # A three-colon location splits from the right into file 'w:x', line 'y', col 'z'.
    got3 = format_github(_report(_diag("w:x:y:z", rule_id="HC-R001")))
    if "::error file=w:x,line=y,col=z," not in got3:
        bad.append(
            f"format_github widened the right-split of a three-colon location; got {got3!r}"
        )

    # A warning finding takes the '::warning' command, not '::error'.
    warn = format_github(_report(_diag("src/y.py:3:1", rule_id="HC-P001",
                                       severity="warning"), errors=0, warnings=1))
    if "::warning file=src/y.py,line=3,col=1," not in warn:
        bad.append(f"format_github did not render a '::warning' line; got {warn!r}")

    # The format dispatch binds the github word to this renderer.
    if by_format.get("github") is not format_github:
        bad.append(
            f"by_format['github'] -> {by_format.get('github')!r}, expected format_github"
        )

    return bad
