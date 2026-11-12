"""honest-errors: the error-policy leaf of the Honest Framework (spec section 1).

A pure leaf: it normalizes raw failure payloads into one canonical ExceptionReport, decides what
should happen to a report as a pure function of the environment, and throttles repeat notifications
with a pure, state-threaded rate-limiter. It touches no file, clock, environment or network; faults
travel as data. It depends only on honest-type, whose Result and Fault it references by name.
"""

from honest_errors.behaviors import BEHAVIORS_BY_ENV, behaviors_for, should_bypass_dedup
from honest_errors.classify import classify_js_payload, classify_py_payload
from honest_errors.email_body import format_email_body
from honest_errors.ir import (
    DedupKey,
    ExceptionReport,
    HandlerBehavior,
    JSErrorPayload,
    PythonExceptionPayload,
    RateLimitConfig,
    RateLimitDecision,
    State,
)
from honest_errors.throttle import check_rate_limit, dedup_key, new_state
from honest_errors.vocabularies import (
    BEHAVIOR_NAMES,
    ENVIRONMENTS,
    SEVERITIES,
    SUPPRESS_REASONS,
)

# __all__ is exactly the declared import surface: the eight functions the .hd names as entry targets
# (the `entry "import honest_errors" -> ...` lines). The four bounded vocabularies and the IR
# TypedDicts are imported above so they remain importable module attributes, but they are supporting
# data and types, not the declared surface, so they do not belong in __all__ (crossed by HC-REF005).
__all__ = [
    "classify_js_payload",
    "classify_py_payload",
    "should_bypass_dedup",
    "behaviors_for",
    "dedup_key",
    "new_state",
    "check_rate_limit",
    "format_email_body",
]
