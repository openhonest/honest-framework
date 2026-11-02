"""format_human renders the human-readable default: the adoption line, one block per
diagnostic, and a 'Found N errors, M warnings.' tally.

The adoption line names the level and the enforced-of-total count. Each finding renders
its split source location as 'file:line:col', its message on an indented line, its
context on a '  | ' line only when the context is non-empty, and a blank line after the
block. The whole is joined with newlines. A location with three colons is split from the
right into exactly file, line and col, so the split keeps the leading path intact rather
than falling back to the whole string.
"""


def _diag(source_location, rule_id="HC-P003", severity="error", context="class X:"):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": "class declaration",
        "source_location": source_location,
        "context": context,
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


def probe_format_human():
    try:
        from honest_check import format_human
    except ImportError as exc:
        return [f"cannot import format_human: {exc}"]

    bad = []

    got = format_human(_report(_diag("src/x.py:10:1")))
    if not isinstance(got, str):
        return [f"format_human(report) -> {got!r}, expected a string"]

    # The adoption line carries both halves: the level phrase and the count phrase.
    if "honest-check: adoption level Declared" not in got:
        bad.append(f"format_human is missing the adoption level phrase; got {got!r}")
    if "50 of 50 rules enforced." not in got:
        bad.append(f"format_human is missing the enforced-count phrase; got {got!r}")

    # The split location renders file:line:col, not the whole location padded with
    # empty line and col. A right-split from a two-colon location gives this exact line.
    if "src/x.py:10:1: error HC-P003" not in got:
        bad.append(f"format_human did not render the split location line; got {got!r}")

    # The message renders on its own indented line.
    if "\n  class declaration\n" not in got:
        bad.append(f"format_human did not render the message line; got {got!r}")

    # A non-empty context renders on a '  | ' line.
    if "\n  | class X:\n" not in got:
        bad.append(f"format_human did not render the context line; got {got!r}")

    # The per-diagnostic blank line and the newline join put a blank line before the
    # tally, and the tally reports the exact error and warning counts.
    if "\n\nFound 1 errors, 0 warnings." not in got:
        bad.append(
            f"format_human did not render a blank line before the tally; got {got!r}"
        )

    # A three-colon location splits from the right into file 'w:x', line 'y', col 'z',
    # keeping the leading colon in the path rather than widening the split.
    got3 = format_human(_report(_diag("w:x:y:z", rule_id="HC-R001")))
    if "w:x:y:z: error HC-R001" not in got3:
        bad.append(
            f"format_human widened the right-split of a three-colon location; got {got3!r}"
        )

    # An empty context renders no '  | ' line at all, and the finding still appears.
    no_context = format_human(_report(_diag("src/y.py:3:1", rule_id="HC-P001",
                                            severity="warning", context=""),
                                      errors=0, warnings=1))
    if "  | " in no_context:
        bad.append(
            f"format_human rendered a context line for an empty context; got {no_context!r}"
        )
    if "HC-P001" not in no_context:
        bad.append(f"format_human(no-context report) is missing 'HC-P001'; got {no_context!r}")

    return bad
