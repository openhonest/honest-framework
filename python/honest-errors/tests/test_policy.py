import os

import pytest

from honest_errors import (
    behaviors_for,
    format_email_body,
    should_bypass_dedup,
    translate_js_payload,
    translate_py_payload,
)


def test_behaviors_development():
    b = behaviors_for("development")
    names = [x["name"] for x in b]
    assert names == ["log", "reraise"]


def test_behaviors_production():
    b = behaviors_for("production")
    names = [x["name"] for x in b]
    assert names == ["log", "email"]


def test_behaviors_test():
    assert [b["name"] for b in behaviors_for("test")] == ["log"]


def test_behaviors_unknown_falls_back_to_development():
    assert [b["name"] for b in behaviors_for("staging")] == ["log", "reraise"]


def test_translate_js_payload_happy():
    payload = {
        "message": "TypeError: x is not a function",
        "source": "app.js",
        "lineno": 10, "colno": 5,
        "stack": "Error\n at app.js:10",
        "url": "https://example.com/p",
        "user_agent": "mozilla",
        "timestamp": "2026-04-23T00:00:00Z",
        "context": {"user_id": "u1"},
    }
    report = translate_js_payload(payload)
    assert report["exception_type"] == "JavaScriptError"
    assert report["file"] == "app.js"
    assert report["line"] == 10
    assert report["context"] == {"user_id": "u1"}


def test_translate_js_payload_critical_severity():
    payload = {
        "message": "CRITICAL database down",
        "source": "x", "lineno": 0, "colno": 0,
        "stack": "", "url": "", "user_agent": "",
        "timestamp": "", "context": {},
    }
    report = translate_js_payload(payload)
    assert report["severity"] == "critical"


def test_translate_py_payload_happy():
    payload = {
        "exception_type": "ValueError",
        "message": "bad value",
        "tb_file": "app.py",
        "tb_line": 42,
        "tb_function": "do_thing",
        "traceback": "Traceback...",
        "context": {"order_id": "o1"},
    }
    report = translate_py_payload(payload)
    assert report["exception_type"] == "ValueError"
    assert report["severity"] == "error"
    assert report["context"] == {"order_id": "o1"}


def test_should_bypass_dedup_critical():
    assert should_bypass_dedup("critical") is True
    assert should_bypass_dedup("error") is False


def test_format_email_body_contains_sections():
    report = {
        "exception_type": "ValueError",
        "message": "bad",
        "severity": "error",
        "environment": "production",
        "file": "app.py", "line": 1, "function": "f",
        "traceback": "Traceback: ...",
        "context": {"user": "alice"},
        "timestamp": "2026-04-23T00:00:00Z",
    }
    body = format_email_body(report)
    assert "ValueError" in body
    assert "production" in body
    assert "app.py" in body
    assert "alice" in body
    assert "Traceback:" in body


def test_format_email_body_truncates_long_context():
    report = {
        "exception_type": "E", "message": "m", "severity": "error",
        "environment": "production", "file": "", "line": 0, "function": "",
        "traceback": "", "context": {"big": "x" * 500},
        "timestamp": "",
    }
    body = format_email_body(report)
    assert "..." in body
