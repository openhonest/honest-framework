"""honest-errors - the error-policy leaf.

One canonical report from two raw payloads; what happens to a report is a pure function of the
environment; repeat notifications are suppressed by a deterministic, state-threaded throttle.
No I/O — logging and sending belong to honest-observe and honest-alerts, which compose this leaf.
"""

from honest_errors.email import format_email_body
from honest_errors.normalize import classify_js_payload, classify_py_payload, should_bypass_dedup
from honest_errors.policy import BEHAVIORS_BY_ENV, behaviors_for
from honest_errors.ratelimit import check_rate_limit, dedup_key, new_state
from honest_errors.report import (
    BEHAVIOR_NAMES,
    ENVIRONMENTS,
    SEVERITIES,
    SUPPRESS_REASONS,
    DedupKey,
    ExceptionReport,
    HandlerBehavior,
    JSErrorPayload,
    PythonExceptionPayload,
    RateLimitConfig,
    RateLimitDecision,
)

__all__ = [
    "classify_js_payload",
    "classify_py_payload",
    "should_bypass_dedup",
    "behaviors_for",
    "BEHAVIORS_BY_ENV",
    "dedup_key",
    "new_state",
    "check_rate_limit",
    "format_email_body",
    "SEVERITIES",
    "ENVIRONMENTS",
    "BEHAVIOR_NAMES",
    "SUPPRESS_REASONS",
    "ExceptionReport",
    "JSErrorPayload",
    "PythonExceptionPayload",
    "HandlerBehavior",
    "DedupKey",
    "RateLimitConfig",
    "RateLimitDecision",
]
