"""honest-errors — central JS + Python error policy.

Distilled from multicardz's exception_handler.py (proven in production).

Environment dispatch:
    development → log + reraise (dev modal catches it client-side)
    production  → log + email (rate-limited: 5-min dedup, 10/hour cap)
    test        → log only
"""
from honest_errors.policy import (
    behaviors_for,
    environment_from_env,
    format_email_body,
    select_behaviors,
    should_bypass_dedup,
    translate_js_payload,
    translate_py_payload,
)
from honest_errors.rate_limit import (
    DedupKey,
    RateLimitConfig,
    RateLimitDecision,
    check_rate_limit,
    dedup_key,
    new_state,
)
from honest_errors.types import (
    EmailEnvelope,
    ExceptionReport,
    HandlerBehavior,
    JSErrorPayload,
    PythonExceptionPayload,
)

__all__ = [
    "DedupKey", "EmailEnvelope", "ExceptionReport", "HandlerBehavior",
    "JSErrorPayload", "PythonExceptionPayload",
    "RateLimitConfig", "RateLimitDecision",
    "behaviors_for", "check_rate_limit", "dedup_key",
    "environment_from_env", "format_email_body", "new_state",
    "select_behaviors", "should_bypass_dedup",
    "translate_js_payload", "translate_py_payload",
]
