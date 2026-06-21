"""Normalization (section 3): two raw payloads to one ExceptionReport, faults as data.

`classify_js_payload` / `classify_py_payload` validate the required keys for their shape and
return a Result — `ok(ExceptionReport)`, or `err(fault 'malformed_payload')` when a key is
missing, never a raised exception. Both are pure: `environment` and `timestamp` are arguments,
never read from the environment or the clock (the boundary that caught the failure already knows
them and passes them in).
"""

from honest_type import err, fault, ok

_JS_REQUIRED = ("message", "source", "lineno", "colno")
_PY_REQUIRED = ("exception_type", "message", "tb_file", "tb_line", "tb_function")


def should_bypass_dedup(severity):
    """Critical failures are never silenced by the throttle (section 3.1). Pure predicate."""
    return severity == "critical"


def _js_severity(payload):
    """Severity for a JS payload (section 3): critical when the message is marked critical, else
    error. A single predicate, not an if-ladder that would grow per rule."""
    return "critical" if "critical" in payload["message"].lower() else "error"


def _missing(payload, required):
    return [key for key in required if key not in payload]


def classify_js_payload(payload, environment, timestamp):
    """Normalize a browser error payload to an ExceptionReport (section 3). Pure."""
    missing = _missing(payload, _JS_REQUIRED)
    if missing:
        return err(fault("malformed_payload", f"JS error payload missing key(s): {missing}", "client", {"missing": missing}))
    return ok(
        {
            "exception_type": "JavaScriptError",
            "message": payload["message"],
            "severity": _js_severity(payload),
            "environment": environment,
            "file": payload["source"],
            "line": payload["lineno"],
            "function": payload.get("function", ""),
            "traceback": payload.get("stack", ""),
            "context": payload.get("context", {}),
            "timestamp": timestamp,
        }
    )


def classify_py_payload(payload, environment, timestamp):
    """Normalize a server exception payload to an ExceptionReport (section 3). Pure. Severity for
    the Python path defaults to error."""
    missing = _missing(payload, _PY_REQUIRED)
    if missing:
        return err(fault("malformed_payload", f"Python exception payload missing key(s): {missing}", "server", {"missing": missing}))
    return ok(
        {
            "exception_type": payload["exception_type"],
            "message": payload["message"],
            "severity": "error",
            "environment": environment,
            "file": payload["tb_file"],
            "line": payload["tb_line"],
            "function": payload["tb_function"],
            "traceback": payload.get("traceback", ""),
            "context": payload.get("context", {}),
            "timestamp": timestamp,
        }
    )
