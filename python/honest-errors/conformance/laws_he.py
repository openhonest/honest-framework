"""honest-errors generative laws (spec sections 2-7).

The suite.json cases pin exact values at representative points. These laws assert the properties that
must hold across a whole bounded vocabulary or over a sequence of calls: every severity obeys the
bypass rule, every environment has a valid policy, removing any one required payload key is reported
as a malformed payload, the rate-limiter threads state without mutating its argument, the JS-severity
marker is a case-insensitive substring, each of the orchestrator's decision paths holds, and the
capture door forwards to the orchestrator unchanged. Each law returns a list of failure strings;
run() prints them and returns an exit code.

Faults travel by return as a bare `X | Fault` union: a fault arm is a dict carrying a `code`, and a
success arm is the value itself (an ExceptionReport, a list, or a FailurePolicy). `check_rate_limit`
answers a `RateLimitOutcome` record `{decision, next_state}`, and a sending decision carries
`reason` `None`.
"""

import copy

import honest_errors
from honest_errors import (
    behaviors_for,
    capture,
    check_rate_limit,
    classify_js_payload,
    classify_py_payload,
    dedup_key,
    handle_failure,
    js_severity,
    new_state,
    should_bypass_dedup,
)

_JS_PAYLOAD = {
    "message": "undefined is not a function",
    "source": "https://app.example/x.js",
    "lineno": 42,
    "colno": 7,
    "stack": "Error\n  at f (x.js:42:7)",
    "url": "https://app.example/page",
    "user_agent": "Mozilla/5.0",
    "timestamp": "2026-01-01T00:00:00Z",
    "context": {},
}

_JS_CRITICAL = {**_JS_PAYLOAD, "message": "Critical: boom"}

_PY_PAYLOAD = {
    "exception_type": "ValueError",
    "message": "bad value",
    "tb_file": "app.py",
    "tb_line": 10,
    "tb_function": "handle",
    "traceback": "Traceback (most recent call last):\n  ValueError: bad value",
    "context": {},
}

_REPORT = {
    "exception_type": "KeyError",
    "message": "missing k",
    "severity": "error",
    "environment": "production",
    "file": "svc.py",
    "line": 73,
    "function": "lookup",
    "traceback": "tb",
    "context": {},
    "timestamp": "2026-03-03T09:00:00Z",
}

_CONFIG = {"dedup_window_seconds": 300, "max_per_hour": 10}
_NOW = 1000.0


def _is_fault(value):
    return isinstance(value, dict) and "code" in value


def law_bypass_iff_critical():
    """§3.1: should_bypass_dedup is true for exactly one severity, critical, across the whole set."""
    out = []
    for severity in honest_errors.SEVERITIES:
        actual = should_bypass_dedup(severity)
        want = severity == "critical"
        if actual is not want:
            out.append(f"should_bypass_dedup({severity!r}) = {actual!r}, expected {want!r}")
    return out


def law_js_severity_marks_critical_by_substring():
    """§3: js_severity returns 'critical' exactly when the message text contains the token 'critical'
    matched case-insensitively, and 'error' otherwise. A near-miss substring is not a match."""
    out = []
    criticals = ["Critical: boom", "CRITICAL", "it was critical here", "critical", "CrItIcAl failure"]
    errors = ["boom", "", "undefined is not a function", "crit", "critic"]
    for message in criticals:
        actual = js_severity(message)
        if actual != "critical":
            out.append(f"js_severity({message!r}) = {actual!r}, expected 'critical'")
    for message in errors:
        actual = js_severity(message)
        if actual != "error":
            out.append(f"js_severity({message!r}) = {actual!r}, expected 'error'")
    return out


def law_every_environment_has_a_valid_policy():
    """§4: behaviors_for returns, for every declared environment, a list whose every name is a
    BEHAVIOR_NAMES word and whose orders are the contiguous 0..n-1."""
    out = []
    for environment in honest_errors.ENVIRONMENTS:
        result = behaviors_for(environment)
        if not isinstance(result, list):
            out.append(f"behaviors_for({environment!r}) = {result!r}, expected a list")
            continue
        for behavior in result:
            if behavior["name"] not in honest_errors.BEHAVIOR_NAMES:
                out.append(f"behaviors_for({environment!r}) has name {behavior['name']!r} outside BEHAVIOR_NAMES")
        orders = [behavior["order"] for behavior in result]
        if orders != list(range(len(result))):
            out.append(f"behaviors_for({environment!r}) orders = {orders}, expected {list(range(len(result)))}")
    return out


def law_unknown_environment_is_a_fault():
    """§4: an environment the table does not carry yields an unknown_environment Fault, never a
    fallback list and never a raise."""
    out = []
    for environment in ("staging", "", "Production", "prod"):
        result = behaviors_for(environment)
        if isinstance(result, list):
            out.append(f"behaviors_for({environment!r}) returned a list; expected an unknown_environment Fault")
            continue
        if not _is_fault(result) or result.get("code") != "unknown_environment":
            out.append(f"behaviors_for({environment!r}) = {result!r}, expected a Fault with code unknown_environment")
    return out


def law_js_missing_any_required_key_is_malformed():
    """§3: removing any one required key of a valid JS payload yields a malformed_payload Fault."""
    out = []
    for key in _JS_PAYLOAD:
        payload = {k: v for k, v in _JS_PAYLOAD.items() if k != key}
        result = classify_js_payload(payload, "production", "2026-02-02T12:00:00Z")
        if not _is_fault(result) or result.get("code") != "malformed_payload":
            out.append(f"classify_js_payload without {key!r} = {result!r}, expected a malformed_payload Fault")
    return out


def law_py_missing_any_required_key_is_malformed():
    """§3: removing any one required key of a valid Python payload yields a malformed_payload Fault."""
    out = []
    for key in _PY_PAYLOAD:
        payload = {k: v for k, v in _PY_PAYLOAD.items() if k != key}
        result = classify_py_payload(payload, "production", "2026-02-02T12:00:00Z")
        if not _is_fault(result) or result.get("code") != "malformed_payload":
            out.append(f"classify_py_payload without {key!r} = {result!r}, expected a malformed_payload Fault")
    return out


def law_classify_stamps_arguments():
    """§3, §1.5: a valid payload stamps the supplied environment and timestamp onto the report, for
    every environment, and the severity is always a SEVERITIES word. The Python path defaults to
    error."""
    out = []
    for environment in honest_errors.ENVIRONMENTS:
        timestamp = f"2026-04-04T00:00:00+00:00/{environment}"
        for name, classify, payload, want_severity in (
            ("js", classify_js_payload, _JS_PAYLOAD, None),
            ("py", classify_py_payload, _PY_PAYLOAD, "error"),
        ):
            result = classify(payload, environment, timestamp)
            if _is_fault(result) or not isinstance(result, dict):
                out.append(f"{name} classify in {environment!r} = {result!r}, expected an ExceptionReport")
                continue
            report = result
            if report["environment"] != environment:
                out.append(f"{name} report environment = {report['environment']!r}, expected {environment!r}")
            if report["timestamp"] != timestamp:
                out.append(f"{name} report timestamp = {report['timestamp']!r}, expected {timestamp!r}")
            if report["severity"] not in honest_errors.SEVERITIES:
                out.append(f"{name} report severity {report['severity']!r} outside SEVERITIES")
            if want_severity is not None and report["severity"] != want_severity:
                out.append(f"{name} report severity = {report['severity']!r}, expected {want_severity!r}")
    return out


def law_dedup_key_projects_three_fields():
    """§5: dedup_key is the exact three-field projection of a report."""
    key = dedup_key(_REPORT)
    want = {"exception_type": _REPORT["exception_type"], "file": _REPORT["file"], "line": _REPORT["line"]}
    if key == want:
        return []
    return [f"dedup_key(_REPORT) = {key!r}, expected {want!r}"]


def law_check_rate_limit_does_not_mutate_state():
    """§5: check_rate_limit returns a new state and never mutates the state it was given."""
    key = {"exception_type": "ValueError", "file": "app.py", "line": 10}
    state = {"dedup_cache": {"x": 500}, "hourly_sends": [500, 900]}
    before = copy.deepcopy(state)
    check_rate_limit(key, _CONFIG, state, 1000)
    if state == before:
        return []
    return [f"check_rate_limit mutated its state argument: {before!r} -> {state!r}"]


def law_rate_limit_dedup_suppresses_a_repeat():
    """§5: a second send of the same key within dedup_window_seconds is suppressed as a duplicate;
    the same key after the window has elapsed is allowed again. A sending decision carries reason
    None."""
    out = []
    key = {"exception_type": "ValueError", "file": "app.py", "line": 10}
    first = check_rate_limit(key, _CONFIG, new_state(), 1000)
    if not first["decision"]["should_send"]:
        out.append(f"first send suppressed: {first['decision']!r}")
    if first["decision"]["reason"] is not None:
        out.append(f"first send reason = {first['decision']['reason']!r}, expected None")
    second = check_rate_limit(key, _CONFIG, first["next_state"], 1100)
    if second["decision"]["should_send"] or second["decision"]["reason"] != "rate_limit_dedup":
        out.append(f"repeat within window = {second['decision']!r}, expected suppressed rate_limit_dedup")
    third = check_rate_limit(key, _CONFIG, first["next_state"], 1400)
    if not third["decision"]["should_send"] or third["decision"]["reason"] is not None:
        out.append(f"repeat after window = {third['decision']!r}, expected allowed with reason None")
    return out


def law_rate_limit_decision_is_consistent():
    """§5: a suppressed decision always carries a SUPPRESS_REASONS word; a sending decision always
    carries reason None."""
    out = []
    key = {"exception_type": "ValueError", "file": "app.py", "line": 10}
    scenarios = (
        ({"dedup_window_seconds": 300, "max_per_hour": 10}, {"dedup_cache": {}, "hourly_sends": []}, 1000),
        ({"dedup_window_seconds": 300, "max_per_hour": 2}, {"dedup_cache": {}, "hourly_sends": [800, 900]}, 1000),
    )
    for config, state, now in scenarios:
        decision = check_rate_limit(key, config, state, now)["decision"]
        if decision["should_send"]:
            if decision["reason"] is not None:
                out.append(f"sending decision carried reason {decision['reason']!r}, expected None")
        elif decision["reason"] not in honest_errors.SUPPRESS_REASONS:
            out.append(f"suppressed decision reason {decision['reason']!r} outside SUPPRESS_REASONS")
    return out


def law_handle_failure_malformed_short_circuits():
    """§3, §7: a malformed payload comes back as a malformed_payload Fault, before any policy is
    built (no FailurePolicy)."""
    bad = {k: v for k, v in _JS_PAYLOAD.items() if k != "message"}
    result = handle_failure("js", bad, "production", "ts", _CONFIG, new_state(), _NOW)
    if _is_fault(result) and result.get("code") == "malformed_payload":
        return []
    return [f"handle_failure on a malformed payload = {result!r}, expected a malformed_payload Fault"]


def law_handle_failure_unknown_environment_faults():
    """§4, §7: a clean payload in an environment the policy table does not carry comes back as an
    unknown_environment Fault, not a FailurePolicy."""
    result = handle_failure("py", _PY_PAYLOAD, "staging", "ts", _CONFIG, new_state(), _NOW)
    if _is_fault(result) and result.get("code") == "unknown_environment":
        return []
    return [f"handle_failure in an unknown environment = {result!r}, expected an unknown_environment Fault"]


def law_handle_failure_sends_in_production():
    """§4, §5, §6, §7: a clean non-critical payload in production, on a fresh throttle, yields a
    FailurePolicy that sends, with the production behaviors and a non-empty email body."""
    out = []
    result = handle_failure("py", _PY_PAYLOAD, "production", "ts", _CONFIG, new_state(), _NOW)
    if _is_fault(result):
        return [f"handle_failure (production send) = {result!r}, expected a FailurePolicy"]
    if not result["decision"]["should_send"]:
        out.append(f"decision = {result['decision']!r}, expected should_send True")
    if result["behaviors"] != [{"name": "log", "order": 0}, {"name": "email", "order": 1}]:
        out.append(f"behaviors = {result['behaviors']!r}, expected production's log+email")
    if not result["email_body"]:
        out.append("email_body is empty, expected the rendered notification text")
    if result["report"]["environment"] != "production":
        out.append(f"report environment = {result['report']['environment']!r}, expected production")
    return out


def law_handle_failure_suppresses_with_empty_body():
    """§5, §7: when the throttle suppresses a non-critical report, the FailurePolicy does not send and
    carries an empty email body."""
    out = []
    state = {"dedup_cache": {}, "hourly_sends": [950.0]}
    config = {"dedup_window_seconds": 300, "max_per_hour": 1}
    result = handle_failure("py", _PY_PAYLOAD, "production", "ts", config, state, _NOW)
    if _is_fault(result):
        return [f"handle_failure (suppressed) = {result!r}, expected a FailurePolicy"]
    if result["decision"]["should_send"]:
        out.append(f"decision = {result['decision']!r}, expected should_send False")
    if result["email_body"] != "":
        out.append(f"email_body = {result['email_body']!r}, expected the empty string")
    return out


def law_handle_failure_critical_bypasses_the_throttle():
    """§3.1, §7: a critical report produces a non-empty email body even when the throttle would
    suppress it. The bypass forces the notification through."""
    out = []
    state = {"dedup_cache": {}, "hourly_sends": [950.0]}
    config = {"dedup_window_seconds": 300, "max_per_hour": 1}
    result = handle_failure("js", _JS_CRITICAL, "production", "ts", config, state, _NOW)
    if _is_fault(result):
        return [f"handle_failure (critical bypass) = {result!r}, expected a FailurePolicy"]
    if result["report"]["severity"] != "critical":
        out.append(f"report severity = {result['report']['severity']!r}, expected critical")
    if not result["email_body"]:
        out.append("email_body is empty, expected a non-empty body despite the throttle (bypass)")
    return out


def law_capture_forwards_to_handle_failure():
    """§7: capture transforms nothing — for the same inputs it returns exactly what handle_failure
    returns, on a sending path and on a fault path."""
    out = []
    send_args = ("py", _PY_PAYLOAD, "production", "ts", _CONFIG, new_state(), _NOW)
    if capture(*send_args) != handle_failure(*send_args):
        out.append("capture != handle_failure on a sending path")
    bad = {k: v for k, v in _JS_PAYLOAD.items() if k != "message"}
    fault_args = ("js", bad, "production", "ts", _CONFIG, new_state(), _NOW)
    if capture(*fault_args) != handle_failure(*fault_args):
        out.append("capture != handle_failure on a fault path")
    return out


def law_handle_failure_unknown_source_faults():
    """§7: a source that matches no normalizer returns an unknown_source Fault before any policy, never
    a raised KeyError and never a FailurePolicy."""
    result = handle_failure("svg", _PY_PAYLOAD, "production", "ts", _CONFIG, new_state(), _NOW)
    if _is_fault(result) and result.get("code") == "unknown_source":
        return []
    return [f"handle_failure with an unknown source = {result!r}, expected an unknown_source Fault"]


def law_handle_failure_logonly_env_never_emails():
    """§7, conformance 9: a log-only environment (development, test) never carries an email body, even
    when the throttle would send a fresh report and even for a critical severity that bypasses the
    throttle. No email behavior in the policy means no email, whatever the throttle decides."""
    out = []
    for environment in ("development", "test"):
        sending = handle_failure("py", _PY_PAYLOAD, environment, "ts", _CONFIG, new_state(), _NOW)
        if _is_fault(sending):
            out.append(f"handle_failure (log-only send, {environment}) = {sending!r}, expected a FailurePolicy")
        else:
            if not sending["decision"]["should_send"]:
                out.append(f"{environment}: expected should_send True on a fresh throttle, got {sending['decision']!r}")
            if sending["email_body"] != "":
                out.append(f"{environment}: email_body = {sending['email_body']!r}, expected empty (no email behavior)")
        critical = handle_failure("js", _JS_CRITICAL, environment, "ts", _CONFIG, new_state(), _NOW)
        if _is_fault(critical):
            out.append(f"handle_failure (log-only critical, {environment}) = {critical!r}, expected a FailurePolicy")
        elif critical["email_body"] != "":
            out.append(f"{environment}: critical email_body = {critical['email_body']!r}, expected empty (no email behavior even on bypass)")
    return out


_LAWS = (
    law_bypass_iff_critical,
    law_js_severity_marks_critical_by_substring,
    law_every_environment_has_a_valid_policy,
    law_unknown_environment_is_a_fault,
    law_js_missing_any_required_key_is_malformed,
    law_py_missing_any_required_key_is_malformed,
    law_classify_stamps_arguments,
    law_dedup_key_projects_three_fields,
    law_check_rate_limit_does_not_mutate_state,
    law_rate_limit_dedup_suppresses_a_repeat,
    law_rate_limit_decision_is_consistent,
    law_handle_failure_malformed_short_circuits,
    law_handle_failure_unknown_environment_faults,
    law_handle_failure_sends_in_production,
    law_handle_failure_suppresses_with_empty_body,
    law_handle_failure_critical_bypasses_the_throttle,
    law_capture_forwards_to_handle_failure,
    law_handle_failure_unknown_source_faults,
    law_handle_failure_logonly_env_never_emails,
)


def run():
    passed = 0
    failed = 0
    for law in _LAWS:
        failures = law()
        if failures:
            failed += 1
            for failure in failures:
                print(f"FAIL {law.__name__}: {failure}")
        else:
            passed += 1
    print(f"laws: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(run())
