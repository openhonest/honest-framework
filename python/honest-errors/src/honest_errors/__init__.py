"""honest-errors: the error-policy module.

A raw failure payload arrives from the outside world (a browser's JavaScript error object, or a
server's Python exception), honest-errors normalizes it into one canonical ExceptionReport, decides
what should happen to that report as a pure function of the environment, and throttles repeat
notifications. It records nothing and sends nothing: honest-observe records the report as an event and
honest-alerts delivers any notification.

The world enters through the capture door, which forwards to the handle_failure orchestrator; the
orchestrator runs normalize -> behaviors -> throttle -> render and assembles one FailurePolicy. The
pure core (classify, behaviors, throttle, email body) and the new_state seed carry the rest. No
function reads a file, a clock, or the environment: environment, timestamp and now are arguments.
"""

from honest_errors.behaviors import behaviors_for
from honest_errors.classify import (
    classify_js_payload,
    classify_py_payload,
    js_severity,
    normalize_by_source,
    should_bypass_dedup,
)
from honest_errors.compose import capture, handle_failure
from honest_errors.email_body import format_email_body
from honest_errors.ir import (
    DedupKey,
    ExceptionReport,
    Fault,
    FailurePolicy,
    HandlerBehavior,
    JSErrorPayload,
    PythonExceptionPayload,
    RateLimitConfig,
    RateLimitDecision,
    RateLimitOutcome,
    RateState,
)
from honest_errors.throttle import check_rate_limit, dedup_key, new_state
from honest_errors.vocabularies import (
    BEHAVIOR_NAMES,
    ENVIRONMENTS,
    PAYLOAD_SOURCES,
    SEVERITIES,
    SUPPRESS_REASONS,
)

# The declared public surface: the eleven functions the .hd declares (HC-REF005 reads this literal
# list). The bounded vocabularies, the dispatch table and the IR TypedDicts are module attributes the
# conformance imports by name; they are not functions, so they are not listed here.
__all__ = [
    # Pure core (sections 3, 4, 5, 6)
    "js_severity",
    "classify_js_payload",
    "classify_py_payload",
    "should_bypass_dedup",
    "behaviors_for",
    "dedup_key",
    "check_rate_limit",
    "format_email_body",
    # The import-surface edge (section 5)
    "new_state",
    # The orchestrator (section 7)
    "handle_failure",
    # The door (section 7)
    "capture",
]

# Re-exported so `import honest_errors; honest_errors.<name>` resolves the vocabularies, the dispatch
# table and the IR the conformance and downstream consumers read. Named here to mark them deliberate.
_REEXPORTED = (
    SEVERITIES,
    ENVIRONMENTS,
    BEHAVIOR_NAMES,
    SUPPRESS_REASONS,
    PAYLOAD_SOURCES,
    normalize_by_source,
    JSErrorPayload,
    PythonExceptionPayload,
    ExceptionReport,
    HandlerBehavior,
    DedupKey,
    RateLimitConfig,
    RateLimitDecision,
    RateState,
    RateLimitOutcome,
    FailurePolicy,
    Fault,
)
