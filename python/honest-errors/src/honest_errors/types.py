from __future__ import annotations

from typing import Any, TypedDict


class JSErrorPayload(TypedDict):
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
    exception_type: str
    message: str
    tb_file: str
    tb_line: int
    tb_function: str
    traceback: str
    context: dict[str, Any]


class ExceptionReport(TypedDict):
    exception_type: str
    message: str
    severity: str        # debug | info | warning | error | critical
    environment: str     # development | production | test
    file: str
    line: int
    function: str
    traceback: str
    context: dict[str, Any]
    timestamp: str


class EmailEnvelope(TypedDict):
    to: str
    subject: str
    body: str


class HandlerBehavior(TypedDict):
    name: str           # "log" | "email" | "reraise"
    order: int
