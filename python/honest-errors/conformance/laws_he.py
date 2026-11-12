"""honest-errors generative laws (spec sections 2-6).

The suite.json cases pin exact values at representative points. These laws assert the properties that
must hold across a whole bounded vocabulary or over a sequence of calls: every severity obeys the
bypass rule, every environment has a valid policy, removing any one required payload key is reported
as a malformed payload, and the rate-limiter threads state without mutating its argument. Each law
returns a list of failure strings; run() prints them and returns an exit code.
"""

import copy

import honest_errors
from honest_errors import (
    behaviors_for,
    check_rate_limit,
    classify_js_payload,
    classify_py_payload,
    dedup_key,
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


def law_bypass_iff_critical():
    """§3.1: should_bypass_dedup is true for exactly one severity, critical, across the whole set."""
    out = []
    for severity in honest_errors.SEVERITIES:
        actual = should_bypass_dedup(severity)
        want = severity == "critical"
        if actual is not want:
            out.append(f"should_bypass_dedup({severity!r}) = {actual!r}, expected {want!r}")
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
        if not isinstance(result, dict) or result.get("code") != "unknown_environment":
            out.append(f"behaviors_for({environment!r}) = {result!r}, expected a Fault with code unknown_environment")
    return out


def law_js_missing_any_required_key_is_malformed():
    """§3: removing any one required key of a valid JS payload yields an err malformed_payload."""
    out = []
    for key in _JS_PAYLOAD:
        payload = {k: v for k, v in _JS_PAYLOAD.items() if k != key}
        result = classify_js_payload(payload, "production", "2026-02-02T12:00:00Z")
        if "err" not in result or result["err"].get("code") != "malformed_payload":
            out.append(f"classify_js_payload without {key!r} = {result!r}, expected err malformed_payload")
    return out


def law_py_missing_any_required_key_is_malformed():
    """§3: removing any one required key of a valid Python payload yields an err malformed_payload."""
    out = []
    for key in _PY_PAYLOAD:
        payload = {k: v for k, v in _PY_PAYLOAD.items() if k != key}
        result = classify_py_payload(payload, "production", "2026-02-02T12:00:00Z")
        if "err" not in result or result["err"].get("code") != "malformed_payload":
            out.append(f"classify_py_payload without {key!r} = {result!r}, expected err malformed_payload")
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
            if "ok" not in result:
                out.append(f"{name} classify in {environment!r} = {result!r}, expected ok")
                continue
            report = result["ok"]
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
    config = {"dedup_window_seconds": 300, "max_per_hour": 10}
    state = {"dedup_cache": {"x": 500}, "hourly_sends": [500, 900]}
    before = copy.deepcopy(state)
    check_rate_limit(key, config, state, 1000)
    if state == before:
        return []
    return [f"check_rate_limit mutated its state argument: {before!r} -> {state!r}"]


def law_rate_limit_dedup_suppresses_a_repeat():
    """§5: a second send of the same key within dedup_window_seconds is suppressed as a duplicate;
    the same key after the window has elapsed is allowed again."""
    out = []
    key = {"exception_type": "ValueError", "file": "app.py", "line": 10}
    config = {"dedup_window_seconds": 300, "max_per_hour": 10}
    decision1, state1 = check_rate_limit(key, config, new_state(), 1000)
    if not decision1["should_send"]:
        out.append(f"first send suppressed: {decision1!r}")
    decision2, state2 = check_rate_limit(key, config, state1, 1100)
    if decision2["should_send"] or decision2["reason"] != "rate_limit_dedup":
        out.append(f"repeat within window = {decision2!r}, expected suppressed rate_limit_dedup")
    decision3, _ = check_rate_limit(key, config, state1, 1400)
    if not decision3["should_send"] or decision3["reason"] != "":
        out.append(f"repeat after window = {decision3!r}, expected allowed with empty reason")
    return out


def law_rate_limit_decision_is_consistent():
    """§5: a suppressed decision always carries a SUPPRESS_REASONS word; an allowed decision always
    carries the empty reason."""
    out = []
    key = {"exception_type": "ValueError", "file": "app.py", "line": 10}
    scenarios = (
        ({"dedup_window_seconds": 300, "max_per_hour": 10}, {"dedup_cache": {}, "hourly_sends": []}, 1000),
        ({"dedup_window_seconds": 300, "max_per_hour": 2}, {"dedup_cache": {}, "hourly_sends": [800, 900]}, 1000),
    )
    for config, state, now in scenarios:
        decision, _ = check_rate_limit(key, config, state, now)
        if decision["should_send"]:
            if decision["reason"] != "":
                out.append(f"allowed decision carried reason {decision['reason']!r}, expected empty")
        elif decision["reason"] not in honest_errors.SUPPRESS_REASONS:
            out.append(f"suppressed decision reason {decision['reason']!r} outside SUPPRESS_REASONS")
    return out


_LAWS = (
    law_bypass_iff_critical,
    law_every_environment_has_a_valid_policy,
    law_unknown_environment_is_a_fault,
    law_js_missing_any_required_key_is_malformed,
    law_py_missing_any_required_key_is_malformed,
    law_classify_stamps_arguments,
    law_dedup_key_projects_three_fields,
    law_check_rate_limit_does_not_mutate_state,
    law_rate_limit_dedup_suppresses_a_repeat,
    law_rate_limit_decision_is_consistent,
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
