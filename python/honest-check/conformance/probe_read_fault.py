"""Honest probe for honest-check's read_fault (feature Scenario: read_fault).

read_fault builds honest-check's own {problem, remedy} Fault off the boundary from
the raw read-failure reason read_declaration returned: problem carries what went
wrong (the reason), and remedy states what to do instead. It is pure. Each case
feeds a distinctive reason string and demands a two-field Fault back whose problem
carries the reason verbatim and whose remedy is a non-empty instruction. A stub
returning {} or empty fields fails on the missing keys or the uncarried reason.

The exact wording of problem and remedy is not pinned by the scenario or the .hd,
so this probe pins the one claim they fix: the Fault has both fields and the reason
is carried into problem. See the GAPS note in the accompanying report.
"""

# Each case: a raw read-failure reason, and the field assertions the Fault must satisfy.
_CASES = [
    {"reason": "mod.hd does not exist"},
    {"reason": "honest-design could not parse mod.hd: unexpected token at line 3"},
]


def probe_read_fault():
    """read_fault builds a two-field Fault that carries the read-failure reason."""
    try:
        from honest_check import read_fault
    except ImportError as exc:
        return [f"cannot import read_fault: {exc}"]

    bad = []
    for case in _CASES:
        reason = case["reason"]
        got = read_fault(reason=reason)
        if not isinstance(got, dict) or "problem" not in got or "remedy" not in got:
            bad.append(f"read_fault({reason!r}) -> {got!r}, expected a {{problem, remedy}} Fault")
            continue
        if reason not in got["problem"]:
            bad.append(
                f"read_fault({reason!r}).problem = {got['problem']!r}, "
                f"expected it to carry the reason {reason!r}"
            )
        if not got["remedy"]:
            bad.append(
                f"read_fault({reason!r}).remedy = {got['remedy']!r}, "
                f"expected a non-empty remedy instruction"
            )
    return bad
