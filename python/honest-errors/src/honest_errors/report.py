"""The report IR and bounded vocabularies (section 2): all data, no behaviour.

Two raw payload shapes (browser JavaScript, server Python) collapse to one `ExceptionReport`
so every consumer — the observe event, the alerts notification, the email body — is
source-agnostic. The four vocabularies are closed frozensets: honest-test enumerates them,
honest-check treats them as discriminant sets. Everything here is TypedDict; no classes, no
methods.
"""

from typing import Any, TypedDict

SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
ENVIRONMENTS = frozenset({"development", "production", "test"})
BEHAVIOR_NAMES = frozenset({"log", "email", "reraise"})
SUPPRESS_REASONS = frozenset({"rate_limit_hourly", "rate_limit_dedup"})


class JSErrorPayload(TypedDict, total=False):
    message: str
    source: str
    lineno: int
    colno: int
    stack: str
    url: str
    user_agent: str
    timestamp: str
    context: dict[str, Any]


class PythonExceptionPayload(TypedDict, total=False):
    exception_type: str
    message: str
    tb_file: str
    tb_line: int
    tb_function: str
    traceback: str
    context: dict[str, Any]


class ExceptionReport(TypedDict):
    exception_type: str
    message: str
    severity: str
    environment: str
    file: str
    line: int
    function: str
    traceback: str
    context: dict[str, Any]
    timestamp: str


class HandlerBehavior(TypedDict):
    name: str
    order: int


class DedupKey(TypedDict):
    exception_type: str
    file: str
    line: int


class RateLimitConfig(TypedDict):
    dedup_window_seconds: float
    max_per_hour: int


class RateLimitDecision(TypedDict):
    should_send: bool
    reason: str
