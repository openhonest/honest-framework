"""Normalization (spec section 3): the two payload shapes collapse to one canonical ExceptionReport.

Each normalizer validates the raw payload against the required keys of its shape and returns a Result
whose err arm is a malformed_payload Fault naming the missing keys, otherwise a Result whose ok arm is
the ten-field ExceptionReport. environment and timestamp are arguments stamped onto the report, never
read from os.getenv or a clock (spec section 1.5). A fault travels as data; nothing raises.
"""

from honest_type import err, fault, ok

_JS_REQUIRED = ("message", "source", "lineno", "colno", "stack", "url", "user_agent", "timestamp", "context")

_PY_REQUIRED = ("exception_type", "message", "tb_file", "tb_line", "tb_function", "traceback", "context")


def classify_js_payload(payload, environment, timestamp):
    """Normalize a raw browser-JavaScript error payload into one canonical ExceptionReport (spec
    section 3). Severity is derived from the payload by a nested predicate: a message marked critical
    yields critical, else error. The JS payload carries no exception type or enclosing function, so the
    report stamps a fixed JavaScriptError type and an empty function (a spec gap, see the module
    report)."""
    missing = [key for key in _JS_REQUIRED if key not in payload]
    if missing:
        return err(fault(
            code="malformed_payload",
            message=f"JS error payload is missing required keys {missing}; a JSErrorPayload must carry {list(_JS_REQUIRED)}",
            category="client",
            results=[],
            detail={"missing": missing, "shape": "JSErrorPayload"},
        ))

    def _severity_of(message):
        return "critical" if "critical" in message.lower() else "error"

    report = {
        "exception_type": "JavaScriptError",
        "message": payload["message"],
        "severity": _severity_of(payload["message"]),
        "environment": environment,
        "file": payload["source"],
        "line": payload["lineno"],
        "function": "",
        "traceback": payload["stack"],
        "context": payload["context"],
        "timestamp": timestamp,
    }
    return ok(report)


def classify_py_payload(payload, environment, timestamp):
    """Normalize a raw server-side Python exception payload into the same ten-field ExceptionReport
    decomposition classify_js_payload produces, at the Python path's default severity error (spec
    section 3)."""
    missing = [key for key in _PY_REQUIRED if key not in payload]
    if missing:
        return err(fault(
            code="malformed_payload",
            message=f"Python exception payload is missing required keys {missing}; a PythonExceptionPayload must carry {list(_PY_REQUIRED)}",
            category="client",
            results=[],
            detail={"missing": missing, "shape": "PythonExceptionPayload"},
        ))

    report = {
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
    return ok(report)
