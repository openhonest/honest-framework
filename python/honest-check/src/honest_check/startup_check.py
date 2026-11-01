"""The development-mode startup door (honest-check.hd: startup_check, role boundary_in).

The host application calls it with the source paths; it hands them to
check_paths, keeps the findings from the startup-eligible rules, decides whether
any kept finding reaches the blocking severity, acts per on_error, and returns
the startup-eligible diagnostics.

At startup only the startup_rules set runs — the parse gate HC-SYN plus the
construction-time and light static rules (HC001, HC002, HC003, HC006, HC007,
HC011, HC-SM01, HC-SM02, HC-SM05) — because the full-codebase AST rules are too
slow as the host boots. The kept findings are filtered to that set here.

severity is the minimum severity a diagnostic must reach to count as a block,
one of 'error', 'warning' or 'info'; info < warning < error. A finding below the
threshold never triggers on_error. on_error is exactly one of three words,
dispatched through a table that closes its open input with a no-match row:
'warn' prints the blocking findings to stderr and returns them, 'raise' raises
HonestCheckError carrying the report, 'halt' prints and exits the process with
code 1. HonestCheckError is the one typed exception honest-check raises, and
only at this door.
"""

import sys

from honest_check.check_paths import check_paths
from honest_check.types import Diagnostic

# The ten startup-eligible rules (honest-check.hd: startup_rules). Only findings
# from these are kept at startup; the full catalogue runs in CLI mode.
_STARTUP_RULES = frozenset(
    {
        "HC001",
        "HC002",
        "HC003",
        "HC006",
        "HC007",
        "HC011",
        "HC-SM01",
        "HC-SM02",
        "HC-SM05",
        "HC-SYN",
    }
)

# The three severity words in order, so "reaches the threshold" is a rank
# comparison. info < warning < error.
_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


class HonestCheckError(Exception):
    """The one typed exception honest-check raises, and only at this door.

    It carries the blocking report. Raised on the 'raise' path when a finding
    reaches the threshold, and on a malformed on_error, which is a program bug
    at the boundary rather than a value a caller can act on.
    """


def _render(findings: list[Diagnostic]) -> str:
    """One line per blocking finding, for stderr and for the raised report."""
    return "\n".join(
        f"{d['source_location']}: {d['severity']}: {d['rule_id']}: {d['message']}"
        for d in findings
    )


def _warn(startup_findings: list[Diagnostic], blocking: list[Diagnostic]) -> list[Diagnostic]:
    """Print the blocking findings to stderr and let startup continue."""
    print(_render(blocking), file=sys.stderr)
    return startup_findings


def _raise(startup_findings: list[Diagnostic], blocking: list[Diagnostic]) -> list[Diagnostic]:
    """Stop startup by exception, carrying the full report."""
    raise HonestCheckError(_render(blocking))


def _halt(startup_findings: list[Diagnostic], blocking: list[Diagnostic]) -> list[Diagnostic]:
    """Print the blocking findings to stderr, then exit the process with code 1."""
    print(_render(blocking), file=sys.stderr)
    sys.exit(1)


_ON_ERROR = {
    "warn": _warn,
    "raise": _raise,
    "halt": _halt,
}


def _reaches(found_severity: str, threshold: str) -> bool:
    """True when a finding's severity reaches the blocking threshold."""
    return _SEVERITY_RANK[found_severity] >= _SEVERITY_RANK[threshold]


def startup_check(paths: list[str], on_error: str, severity: str) -> list[Diagnostic]:
    """Hand paths to check_paths, keep the startup-eligible findings, and act on
    on_error when a finding reaches the severity threshold."""
    startup_findings = [
        finding
        for finding in check_paths(paths)
        if finding["rule_id"] in _STARTUP_RULES
    ]
    blocking = [
        finding
        for finding in startup_findings
        if _reaches(finding["severity"], severity)
    ]
    if not blocking:
        return startup_findings
    if on_error not in _ON_ERROR:
        accepted = sorted(_ON_ERROR)
        raise HonestCheckError(
            f"on_error {on_error!r} matched no branch; accepted values are "
            f"{accepted} (arrived {on_error!r})"
        )
    return _ON_ERROR[on_error](startup_findings, blocking)
