"""Normalization (architecture section 3).

Two normalizers collapse the two foreign payload shapes onto the one canonical ExceptionReport. Each
validates its payload against the required keys and returns a malformed_payload Fault when any is
absent, otherwise the report. environment and timestamp are arguments, never read from the environment
or a clock here. Which normalizer runs is picked by the payload's source through the normalize_by_source
dispatch table, not a branch.
"""

from honest_errors.ir import JS_REQUIRED_KEYS, PY_REQUIRED_KEYS


def js_severity(message):
    """Derive a JS failure's severity from its message (section 3): 'critical' when the message text
    contains the token 'critical' matched case-insensitively, 'error' for every other message. A
    predicate, not an if/elif ladder that grows a branch per rule."""
    return "critical" if "critical" in message.lower() else "error"


def classify_js_payload(payload, environment, timestamp):
    """Normalize a raw browser JSErrorPayload into one ExceptionReport (section 3). A required key
    absent yields a malformed_payload Fault; otherwise the browser fields map onto the report, severity
    comes from js_severity, and the passed-in environment and timestamp are carried through. The
    browser carries no exception type or function name, so those fold to the generic 'Error' and the
    empty string; colno, url and user_agent, which the report has no column for, fold into context so
    they are not lost."""
    missing = sorted(key for key in JS_REQUIRED_KEYS if key not in payload)
    if missing:
        return {
            "code": "malformed_payload",
            "message": f"a JS error payload is missing required key(s) {missing}; a browser payload must carry {sorted(JS_REQUIRED_KEYS)}",
        }
    return {
        "exception_type": "Error",
        "message": payload["message"],
        "severity": js_severity(payload["message"]),
        "environment": environment,
        "file": payload["source"],
        "line": payload["lineno"],
        "function": "",
        "traceback": payload["stack"],
        "context": {
            **payload["context"],
            "colno": payload["colno"],
            "url": payload["url"],
            "user_agent": payload["user_agent"],
        },
        "timestamp": timestamp,
    }


def classify_py_payload(payload, environment, timestamp):
    """Normalize a raw server PythonExceptionPayload into one ExceptionReport (section 3). A required
    key absent yields a malformed_payload Fault; otherwise exception_type, message, tb_file, tb_line,
    tb_function and traceback map onto the report, severity defaults to 'error', and the passed-in
    environment and timestamp are carried through."""
    missing = sorted(key for key in PY_REQUIRED_KEYS if key not in payload)
    if missing:
        return {
            "code": "malformed_payload",
            "message": f"a Python exception payload is missing required key(s) {missing}; a server payload must carry {sorted(PY_REQUIRED_KEYS)}",
        }
    return {
        "exception_type": payload["exception_type"],
        "message": payload["message"],
        "severity": "error",
        "environment": environment,
        "file": payload["tb_file"],
        "line": payload["tb_line"],
        "function": payload["tb_function"],
        "traceback": payload["traceback"],
        "context": payload["context"],
        "timestamp": timestamp,
    }


def should_bypass_dedup(severity):
    """The one product rule honest-errors carries, as data not control flow (section 3.1): True if and
    only if severity is 'critical'. A critical failure is never silenced by the throttle."""
    return severity == "critical"


# The normalize dispatch (section 3): which normalizer runs is picked by the payload's source, a table
# not a branch. The orchestrator reads it under a no-match guard, so an unknown source faults rather
# than raising a silent KeyError.
normalize_by_source = {
    "js": classify_js_payload,
    "py": classify_py_payload,
}
