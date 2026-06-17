"""Policy: translate payloads, pick behaviors by environment."""
from __future__ import annotations

import os
import time
import traceback
from typing import Any

from honest_errors.types import (
    EmailEnvelope,
    ExceptionReport,
    HandlerBehavior,
    JSErrorPayload,
    PythonExceptionPayload,
)


# --- Environment --------------------------------------------------------


def environment_from_env() -> str:
    return os.getenv("ENV", "development")


# --- Payload → Report ---------------------------------------------------


def translate_js_payload(payload: JSErrorPayload) -> ExceptionReport:
    return ExceptionReport(
        exception_type="JavaScriptError",
        message=payload["message"],
        severity=_js_severity(payload),
        environment=environment_from_env(),
        file=payload.get("source", ""),
        line=payload.get("lineno", 0),
        function="",
        traceback=payload.get("stack", "") or "",
        context=dict(payload.get("context", {})),
        timestamp=payload.get("timestamp", "") or _iso_now(),
    )


def translate_py_payload(payload: PythonExceptionPayload) -> ExceptionReport:
    return ExceptionReport(
        exception_type=payload["exception_type"],
        message=payload["message"],
        severity="error",
        environment=environment_from_env(),
        file=payload.get("tb_file", ""),
        line=payload.get("tb_line", 0),
        function=payload.get("tb_function", ""),
        traceback=payload.get("traceback", ""),
        context=dict(payload.get("context", {})),
        timestamp=_iso_now(),
    )


def _js_severity(payload: JSErrorPayload) -> str:
    msg = (payload.get("message") or "").lower()
    if "critical" in msg:
        return "critical"
    return "error"


def should_bypass_dedup(severity: str) -> bool:
    return severity == "critical"


# --- Behavior dispatch --------------------------------------------------

_BEHAVIORS_BY_ENV: dict[str, list[HandlerBehavior]] = {
    "development": [
        HandlerBehavior(name="log",     order=0),
        HandlerBehavior(name="reraise", order=1),
    ],
    "production": [
        HandlerBehavior(name="log",   order=0),
        HandlerBehavior(name="email", order=1),
    ],
    "test": [
        HandlerBehavior(name="log", order=0),
    ],
}


def behaviors_for(environment: str) -> list[HandlerBehavior]:
    return list(_BEHAVIORS_BY_ENV.get(environment, _BEHAVIORS_BY_ENV["development"]))


# Alias used by honest-check / explorer.
select_behaviors = behaviors_for


# --- Email body formatter -----------------------------------------------


def format_email_body(report: ExceptionReport) -> str:
    lines = [
        "EXCEPTION REPORT",
        "================",
        "",
        f"Severity:    {report['severity']}",
        f"Environment: {report['environment']}",
        f"Time:        {report['timestamp']}",
        "",
        f"Type:     {report['exception_type']}",
        f"Message:  {report['message']}",
        "",
        "Location:",
        f"  File:     {report['file']}",
        f"  Line:     {report['line']}",
        f"  Function: {report['function']}",
        "",
    ]
    if report["context"]:
        lines.append("Context:")
        for k, v in report["context"].items():
            s = str(v)
            if len(s) > 200:
                s = s[:200] + "..."
            lines.append(f"  {k}: {s}")
        lines.append("")
    lines.append("Traceback:")
    lines.append(report["traceback"] or "(no traceback)")
    return "\n".join(lines)


# --- helpers -------------------------------------------------------------


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
