"""Diagnostic types + report aggregator."""
from __future__ import annotations

from typing import TypedDict


class Diagnostic(TypedDict):
    rule_id: str
    severity: str           # "error" | "warning" | "info"
    message: str
    source_location: str    # "path:line"


class CheckReport(TypedDict):
    total_errors: int
    total_warnings: int
    diagnostics: list[Diagnostic]


def aggregate_diagnostics(diagnostics: list[Diagnostic]) -> CheckReport:
    errors = sum(1 for d in diagnostics if d["severity"] == "error")
    warnings = sum(1 for d in diagnostics if d["severity"] == "warning")
    return CheckReport(
        total_errors=errors,
        total_warnings=warnings,
        diagnostics=list(diagnostics),
    )
