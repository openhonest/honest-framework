"""honest-test IR."""
from __future__ import annotations

from typing import Any, Callable, TypedDict


class TestCase(TypedDict):
    name: str
    inputs: dict[str, Any]
    expected: Any


class TestResult(TypedDict):
    name: str
    status: str        # "ok" | "failed" | "errored"
    detail: str


class TestSuite(TypedDict):
    name: str
    results: list[TestResult]
    total_passed: int
    total_failed: int


class Coverage(TypedDict):
    function_name: str
    input_space_size: int
    cases_run: int
    coverage_ratio: float
