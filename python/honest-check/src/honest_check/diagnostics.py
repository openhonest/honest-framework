"""Diagnostic data shape and its constructor.

A diagnostic is plain data: rule id, severity, location, message. No behaviour is
attached. Per honest-check-architecture.md sections 6.1-6.2 the same record drives
every output format. Pure module: no I/O, no global state.
"""

from typing import TypedDict


class Diagnostic(TypedDict):
    """One reported violation. Lines and columns are 1-based (section 6.1)."""

    rule: str
    severity: str  # "error" | "warning" | "info"
    path: str
    line: int
    col: int
    message: str


def diagnostic(
    rule: str,
    severity: str,
    path: str,
    line: int,
    col: int,
    message: str,
) -> Diagnostic:
    """Construct a Diagnostic. Sole constructor so the shape stays in one place."""
    return {
        "rule": rule,
        "severity": severity,
        "path": path,
        "line": line,
        "col": col,
        "message": message,
    }
