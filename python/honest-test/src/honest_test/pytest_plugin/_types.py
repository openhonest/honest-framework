"""Internal TypedDicts for the pytest-plugin layer (M2)."""
from __future__ import annotations

from typing import TypedDict


class HonestTestConfig(TypedDict):
    report_contracts: bool
    report_pytest_items: bool
    lint: bool
    lint_exempt: list[str]
    source_roots: list[str]
    exclude_patterns: list[str]
    private_functions: str  # "skip" | "include"
    coverage_min: int
    coverage_fail_under: bool
    silent_default_params: list[str]
    silent_default_values: list[str]
    silent_default_exempt: list[str]
    silent_default_fail_on_violation: bool
    browser_step_roots: list[str]
    browser_auth_fixture: str
    browser_required_fixture: str
    browser_forbidden_imports: list[str]


class LintViolation(TypedDict):
    path: str
    line: int
    reason: str


class SilentDefaultViolation(TypedDict):
    path: str
    line: int
    function_name: str
    param_name: str
    default_text: str
    signature: str


class ContractStats(TypedDict):
    pytest_items: int
    distinct_contracts: int
    parametrize_ratio: float


class CoverageRow(TypedDict):
    file: str
    pinned: int
    total: int
    function_names: list[tuple[str, bool]]


class CoverageReport(TypedDict):
    rows: list[CoverageRow]
    total_pinned: int
    total_functions: int


class BrowserLintViolation(TypedDict):
    path: str
    line: int
    rule: str   # "B1" .. "B5"
    reason: str
