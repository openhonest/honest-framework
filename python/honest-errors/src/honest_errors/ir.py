"""The report IR of honest-errors (spec section 2, .hd type declarations). All TypedDicts; no classes
and no methods. The two raw payload shapes collapse to one ExceptionReport so every downstream
consumer is source-agnostic.

The vocabulary-bound fields (severity, environment, behavior name, suppression reason) are plain str
here; the closed sets that bound them live in vocabularies.py and are enforced by honest-test, not by
a runtime type.
"""

from typing import Any, TypedDict


class JSErrorPayload(TypedDict):
    """The raw browser-JavaScript error payload classify_js_payload normalizes (spec section 2)."""

    message: str
    source: str
    lineno: int
    colno: int
    stack: str
    url: str
    user_agent: str
    timestamp: str
    context: dict[str, Any]


class PythonExceptionPayload(TypedDict):
    """The raw server-side Python exception payload classify_py_payload normalizes (spec section 2)."""

    exception_type: str
    message: str
    tb_file: str
    tb_line: int
    tb_function: str
    traceback: str
    context: dict[str, Any]


class ExceptionReport(TypedDict):
    """The one canonical report both normalizers produce, the ten-field shape every downstream
    consumer reads (spec section 2). severity is one of SEVERITIES; environment is one of
    ENVIRONMENTS; timestamp is the ISO-8601 time supplied by the caller, never read from a clock."""

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
    """One named behavior in an environment's policy, carried as data (spec section 4). name is one of
    BEHAVIOR_NAMES; order is the 0-based position the behavior runs in within the environment list."""

    name: str
    order: int


class DedupKey(TypedDict):
    """The throttle's identity for a report (spec section 5): the three fields that decide whether two
    failures are the same for deduplication."""

    exception_type: str
    file: str
    line: int


class RateLimitConfig(TypedDict):
    """The throttle's two tunable limits, supplied by the caller (spec section 5)."""

    dedup_window_seconds: int
    max_per_hour: int


class RateLimitDecision(TypedDict):
    """The throttle's answer, returned as data (spec section 5). reason is a SUPPRESS_REASONS word
    when should_send is false, and the empty string when should_send is true."""

    should_send: bool
    reason: str


class State(TypedDict):
    """The throttle's threaded state, owned by the caller and never a module global (spec section 5).
    dedup_cache maps each seen DedupKey (serialized to a string) to the time its last send fired;
    hourly_sends is the list of send times within the trailing hour."""

    dedup_cache: dict[str, int]
    hourly_sends: list[int]
