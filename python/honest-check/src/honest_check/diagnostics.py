"""Diagnostic types + report aggregator (spec §6)."""
from __future__ import annotations

from typing import NotRequired, TypedDict


class Diagnostic(TypedDict):
    rule_id: str
    severity: str            # "error" | "warning" | "info"
    message: str
    source_location: str     # "path:line:col" (human format)
    file: str
    line: int
    col: int
    context: NotRequired[str]
    fixable: NotRequired[bool]


def diagnostic(
    rule_id: str,
    severity: str,
    message: str,
    path: str,
    line: int,
    col: int = 1,
    context: str | None = None,
    fixable: bool = False,
) -> Diagnostic:
    out: Diagnostic = {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": f"{path}:{line}:{col}",
        "file": path,
        "line": line,
        "col": col,
        "fixable": fixable,
    }
    if context is not None:
        out["context"] = context
    return out


class CheckReport(TypedDict):
    total_errors: int
    total_warnings: int
    total_infos: int
    diagnostics: list[Diagnostic]


def aggregate_diagnostics(diagnostics: list[Diagnostic]) -> CheckReport:
    errors = sum(1 for d in diagnostics if d["severity"] == "error")
    warnings = sum(1 for d in diagnostics if d["severity"] == "warning")
    infos = sum(1 for d in diagnostics if d["severity"] == "info")
    return CheckReport(
        total_errors=errors,
        total_warnings=warnings,
        total_infos=infos,
        diagnostics=list(diagnostics),
    )
