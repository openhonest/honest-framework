"""honest-errors conformance runner (sections 2-5).

Each case is data: a normalization case (classify_js/py), a bypass predicate, a behavior-table
lookup, or a rate-limit decision. The email formatter, dedup_key, and the rate-limiter's
state-threading are exercised in laws_he.py.

  uv run --package honest-errors python honest-errors/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_errors import behaviors_for, check_rate_limit, classify_js_payload, classify_py_payload, should_bypass_dedup


def _check_classify(case):
    spec = case["classify"]
    fn = classify_js_payload if spec["fn"] == "js" else classify_py_payload
    result = fn(spec["payload"], spec["environment"], spec["timestamp"])
    if case["expect"] == "ok":
        return "ok" in result and result["ok"] == case["expect_report"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


def _check_bypass(case):
    got = should_bypass_dedup(case["bypass"]["severity"])
    return got == case["expect"], f"got {got}"


def _check_behaviors(case):
    got = behaviors_for(case["behaviors"]["environment"])
    return got == case["expect"], f"got {got}"


def _check_rate_limit(case):
    spec = case["rate_limit"]
    decision, _state = check_rate_limit(spec["key"], spec["config"], spec["state"], spec["now"])
    return decision == case["expect_decision"], f"got {decision}"


_CHECKERS = {
    "classify": _check_classify,
    "bypass": _check_bypass,
    "behaviors": _check_behaviors,
    "rate_limit": _check_rate_limit,
}


def _kind(case):
    for kind in _CHECKERS:
        if kind in case:
            return kind
    return "classify"


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{_kind(case)}]: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_he

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_he.run()
    raise SystemExit(suite_status or laws_status)
