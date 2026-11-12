"""honest-errors conformance runner (spec sections 2-6).

Each case is data: one discriminator key names its kind, and the matching `_check_*` drives the real
function and compares against the expected value. The value cases here pin exact behaviour the spec
fixes; the deeper properties (every severity, every environment, the rate-limiter's state threading
and no-mutation guarantee, each required payload key) are in laws_he.py.

  uv run --package honest-errors python honest-errors/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

import honest_errors
from honest_errors import (
    behaviors_for,
    check_rate_limit,
    classify_js_payload,
    classify_py_payload,
    dedup_key,
    format_email_body,
    new_state,
    should_bypass_dedup,
)

# The twelve-name public surface the spec names: the eight functions (§3-§6) and the four bounded
# vocabularies (§2.1). The exports case checks each is importable, without pinning __all__ exactly,
# because whether the IR TypedDicts also sit in __all__ is not fixed by the spec.
_PUBLIC = (
    "classify_js_payload",
    "classify_py_payload",
    "should_bypass_dedup",
    "behaviors_for",
    "dedup_key",
    "new_state",
    "check_rate_limit",
    "format_email_body",
    "SEVERITIES",
    "ENVIRONMENTS",
    "BEHAVIOR_NAMES",
    "SUPPRESS_REASONS",
)


def _check_vocab(case):
    """A bounded vocabulary (§2.1) is exactly the closed set the spec names, frozen. Catches a member
    dropped, added, or drifted, the whole set missing, and a set left as a plain str container."""
    actual = getattr(honest_errors, case["vocab"], None)
    expect = frozenset(case["expect_members"])
    if not isinstance(actual, frozenset):
        return False, f"{case['vocab']} is {type(actual).__name__}, expected frozenset"
    return actual == expect, f"{case['vocab']} = {actual!r}, expected {expect!r}"


def _check_exports(case):
    """The public surface (§1.4, §2.1, §3-§6): every listed name resolves as a real attribute."""
    missing = [name for name in case["expect_names"] if not hasattr(honest_errors, name)]
    return not missing, f"not importable from honest_errors: {missing}"


def _check_jsclassify(case):
    result = classify_js_payload(case["payload"], case["environment"], case["timestamp"])
    return _check_classify_result(case, result)


def _check_pyclassify(case):
    result = classify_py_payload(case["payload"], case["environment"], case["timestamp"])
    return _check_classify_result(case, result)


def _check_classify_result(case, result):
    if case["expect"] == "err":
        if "err" not in result:
            return False, f"expected err, got {result!r}"
        code = result["err"].get("code")
        return code == case["expect_code"], f"err code = {code!r}, expected {case['expect_code']!r}"
    if "ok" not in result:
        return False, f"expected ok, got {result!r}"
    report = result["ok"]
    fields = {
        "exception_type", "message", "severity", "environment",
        "file", "line", "function", "traceback", "context", "timestamp",
    }
    if set(report.keys()) != fields:
        return False, f"report keys = {sorted(report.keys())}, expected the ten canonical fields"
    if report["environment"] != case["environment"]:
        return False, f"environment = {report['environment']!r}, expected the supplied {case['environment']!r}"
    if report["timestamp"] != case["timestamp"]:
        return False, f"timestamp = {report['timestamp']!r}, expected the supplied {case['timestamp']!r}"
    if report["severity"] != case["expect_severity"]:
        return False, f"severity = {report['severity']!r}, expected {case['expect_severity']!r}"
    if "expect_message" in case and report["message"] != case["expect_message"]:
        return False, f"message = {report['message']!r}, expected {case['expect_message']!r}"
    if "expect_exception_type" in case and report["exception_type"] != case["expect_exception_type"]:
        return False, f"exception_type = {report['exception_type']!r}, expected {case['expect_exception_type']!r}"
    return True, f"ok {report!r}"


def _check_bypass(case):
    actual = should_bypass_dedup(case["severity"])
    return actual is case["expect"], f"should_bypass_dedup({case['severity']!r}) = {actual!r}, expected {case['expect']!r}"


def _check_behaviors(case):
    result = behaviors_for(case["environment"])
    if case["expect"] == "err":
        if not isinstance(result, dict) or "code" not in result:
            return False, f"expected a Fault, got {result!r}"
        return result["code"] == case["expect_code"], f"fault code = {result.get('code')!r}, expected {case['expect_code']!r}"
    return result == case["expect_list"], f"got {result!r}, expected {case['expect_list']!r}"


def _check_dedupkey(case):
    result = dedup_key(case["report"])
    return result == case["expect"], f"got {result!r}, expected {case['expect']!r}"


def _check_newstate(case):
    result = new_state()
    return result == {"dedup_cache": {}, "hourly_sends": []}, f"got {result!r}"


def _check_ratelimit(case):
    decision, state = check_rate_limit(case["key"], case["config"], case["state"], case["now"])
    if decision["should_send"] is not case["expect_should_send"]:
        return False, f"should_send = {decision['should_send']!r}, expected {case['expect_should_send']!r}"
    if decision["reason"] != case["expect_reason"]:
        return False, f"reason = {decision['reason']!r}, expected {case['expect_reason']!r}"
    if "expect_next_hourly" in case and state["hourly_sends"] != case["expect_next_hourly"]:
        return False, f"next hourly_sends = {state['hourly_sends']!r}, expected {case['expect_next_hourly']!r}"
    if "expect_cache_size" in case and len(state["dedup_cache"]) != case["expect_cache_size"]:
        return False, f"next dedup_cache size = {len(state['dedup_cache'])}, expected {case['expect_cache_size']}"
    return True, f"decision {decision!r}"


def _check_emailbody(case):
    body = format_email_body(case["report"])
    if not isinstance(body, str):
        return False, f"body is {type(body).__name__}, expected str"
    missing = [s for s in case["expect_contains"] if s not in body]
    return not missing, f"body missing substrings {missing}: {body!r}"


_CHECKERS = {
    "vocab": _check_vocab,
    "exports": _check_exports,
    "jsclassify": _check_jsclassify,
    "pyclassify": _check_pyclassify,
    "bypass": _check_bypass,
    "behaviors": _check_behaviors,
    "dedupkey": _check_dedupkey,
    "newstate": _check_newstate,
    "ratelimit": _check_ratelimit,
    "emailbody": _check_emailbody,
}


def _kind(case):
    kind = case.get("kind")
    if kind not in _CHECKERS:
        raise ValueError(f"case {case.get('id')!r} names no known kind: {kind!r}")
    return kind


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        if "value_case" in case:
            continue  # value cases are checked centrally by value-check.py; a module cannot run the oracle on itself
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']}: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_he

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_he.run()
    raise SystemExit(suite_status or laws_status)
