"""The report IR and the policy records (architecture sections 2, 4, 5), all TypedDict — no classes,
no methods.

The two foreign payloads copy shapes honest-errors does not own: JSErrorPayload copies a browser's
error object, PythonExceptionPayload copies a CPython exception and its traceback. The canonical
ExceptionReport is the one shape both normalizers collapse to, so every downstream consumer is
source-agnostic. The required-key sets below are the fields each foreign payload must carry; a payload
missing any one is malformed.
"""

from typing import Optional, TypedDict


class JSErrorPayload(TypedDict):
    """A raw browser JavaScript error object (the value window.onerror / the Error event hands the
    capture door). Its fields are the browser's, not honest-errors'."""

    message: str
    source: str
    lineno: int
    colno: int
    stack: str
    url: str
    user_agent: str
    timestamp: str
    context: dict


class PythonExceptionPayload(TypedDict):
    """A raw server Python exception payload (the value a server error boundary hands the door). Its
    fields mirror a CPython exception and traceback."""

    exception_type: str
    message: str
    tb_file: str
    tb_line: int
    tb_function: str
    traceback: str
    context: dict


class ExceptionReport(TypedDict):
    """The one canonical failure report both normalizers produce (section 2)."""

    exception_type: str
    message: str
    severity: str
    environment: str
    file: str
    line: int
    function: str
    traceback: str
    context: dict
    timestamp: str


class HandlerBehavior(TypedDict):
    """One named behavior in a policy (section 4): name in BEHAVIOR_NAMES, order its integer position."""

    name: str
    order: int


class DedupKey(TypedDict):
    """The identity of a failure for de-duplication (section 5)."""

    exception_type: str
    file: str
    line: int


class RateLimitConfig(TypedDict):
    """The throttle's two tunables (section 5), supplied by the caller."""

    dedup_window_seconds: int
    max_per_hour: int


class RateLimitDecision(TypedDict):
    """The throttle's verdict as returned data (section 5): reason is None on send, a SUPPRESS_REASONS
    word on suppress."""

    should_send: bool
    reason: Optional[str]


class RateState(TypedDict):
    """The throttle's state, owned and threaded by the caller (section 5)."""

    dedup_cache: dict
    hourly_sends: list


class RateLimitOutcome(TypedDict):
    """What check_rate_limit returns: the decision for this call and the next state to thread forward."""

    decision: RateLimitDecision
    next_state: RateState


class FailurePolicy(TypedDict):
    """Everything honest-errors decides for one captured failure (section 7), handed back through the
    door. email_body is non-empty only when an email is warranted, the empty string otherwise."""

    report: ExceptionReport
    behaviors: list
    decision: RateLimitDecision
    next_state: RateState
    email_body: str


class Fault(TypedDict):
    """A failure as data (section 8): carried by return, never thrown. code is the fault identifier,
    message says what went wrong and what to do instead."""

    code: str
    message: str


# The fields each foreign payload must carry; a payload missing any one is malformed (section 3).
JS_REQUIRED_KEYS = frozenset(JSErrorPayload.__annotations__)

PY_REQUIRED_KEYS = frozenset(PythonExceptionPayload.__annotations__)
