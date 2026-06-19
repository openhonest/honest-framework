"""Framework startup integration (section 2.3).

An application calls `startup_check(...)` during boot (development mode) to catch
dishonest declarations before serving traffic. It runs the startup-eligible rules
(the fast construction-time checks, section 2.3) and, on errors, warns / raises /
halts per `on_error`. Boundary module: it reads files, writes stderr, and may halt.
"""

# honest: disable HC-P004

import sys
from pathlib import Path

from honest_check.diagnostics import Diagnostic
from honest_check.rules import check_source

# Section 2.3 — only the fast construction-time rules run at startup. (HC-SYN is always
# eligible: unparseable source must fail fast.)
_STARTUP_ELIGIBLE = frozenset(
    {"HC-SYN", "HC001", "HC002", "HC003", "HC006", "HC007", "HC011", "HC-SM01", "HC-SM02", "HC-SM05"}
)


class HonestCheckError(Exception):
    """Raised by startup_check when on_error='raise' and dishonest code is found."""


def _format_report(diagnostics: list[Diagnostic]) -> str:
    return "\n".join(
        f"{d['path']}:{d['line']}:{d['col']}: {d['severity']} {d['rule']} {d['message']}"
        for d in diagnostics
    )


def _on_warn(report: str) -> None:
    print(report, file=sys.stderr)


def _on_raise(report: str) -> None:
    raise HonestCheckError(report)


def _on_halt(report: str) -> None:
    print(report, file=sys.stderr)
    raise SystemExit(1)


_ON_ERROR = {"warn": _on_warn, "raise": _on_raise, "halt": _on_halt}


def _collect(paths: list[str], severity: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for raw in paths:
        path = Path(raw)
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            for d in check_source(file.read_text(encoding="utf-8"), str(file)):
                if d["rule"] in _STARTUP_ELIGIBLE and d["severity"] == severity:
                    out.append(d)
    return out


def startup_check(paths: list[str], on_error: str = "warn", severity: str = "error") -> None:
    """Run the startup-eligible rules over `paths`; handle findings per `on_error`.

    on_error: 'warn' (print to stderr, continue) | 'raise' (HonestCheckError) |
    'halt' (print and exit 1). Returns None when the code is clean.
    """
    diagnostics = _collect(paths, severity)
    if not diagnostics:
        return
    _ON_ERROR.get(on_error, _on_warn)(_format_report(diagnostics))
