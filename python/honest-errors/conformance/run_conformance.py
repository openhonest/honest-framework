"""honest-errors conformance runner — the error-cadence pure core (spec §2-§5).

Each case is data: one `kind` key names its sort, and the matching `_check_*` drives the real
function and compares against the expected value. These cases pin the facts that live cleanly as
JSON data — the bounded vocabularies, the severity grades, the normalizers' fixed report fields and
their malformed-payload fault, the dedup key, and the unknown-preset / unknown-source faults. The
representation-dependent behaviour — the preset Cadences, resolve_cadence's pass-through, the three
build_response outcomes, and the cadence-state transitions, all of which carry honest-errors' own
`Absent` encoding — is asserted in laws_he.py, in Python, against the module's real values.

Scope. The fifteen pure functions. The door `capture`, the orchestrator `handle_failure`, and the
two persistence functions `load_cadence_state` / `store_cadence_state` run through the persistence
boundary and are PARKED until persistence is wired (bead: honest-errors cadence-state persistence).

Faults travel by return as a bare `X | Fault` union, recognized by shape: a fault arm is a dict
carrying a `code`, a success arm is the value itself. No ok/err envelope.

  uv run --package honest-errors python honest-errors/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

import honest_errors
from honest_errors import (
    classify_js_payload,
    classify_py_payload,
    dedup_key,
    js_severity,
    normalize,
    resolve_cadence,
)

# The pure public surface the spec names (§2.1, §3-§5): the fifteen pure functions and the ten
# bounded vocabularies. The exports case checks each is importable, without pinning __all__ exactly.
_PUBLIC = (
    "js_severity", "classify_js_payload", "classify_py_payload", "normalize",
    "preset_silent", "preset_acknowledge", "preset_report_back", "preset_notify",
    "resolve_cadence", "build_response", "dedup_key",
    "expire_elapsed", "release_due", "add_display", "advance_cadence",
    "SEVERITIES", "ENVIRONMENTS", "RESPONSE_MODES", "PAYLOAD_SOURCES", "PRESET_NAMES",
    "ACTION_KINDS", "DISPLAY_STATUSES", "DURATION_KINDS", "TIMING_KINDS", "FAULT_CODES",
)

_REPORT_FIELDS = {
    "exception_type", "message", "severity", "environment",
    "file", "line", "function", "traceback", "context", "timestamp",
}


def _is_fault(value):
    """A fault arm is a dict carrying a `code`; a success arm never does."""
    return isinstance(value, dict) and "code" in value


def _check_vocab(case):
    actual = getattr(honest_errors, case["vocab"], None)
    expect = frozenset(case["expect_members"])
    if not isinstance(actual, frozenset):
        return False, f"{case['vocab']} is {type(actual).__name__}, expected frozenset"
    return actual == expect, f"{case['vocab']} = {actual!r}, expected {expect!r}"


def _check_exports(case):
    missing = [name for name in case["expect_names"] if not hasattr(honest_errors, name)]
    return not missing, f"not importable from honest_errors: {missing}"


def _check_jsseverity(case):
    actual = js_severity(case["message"])
    return actual == case["expect"], f"js_severity({case['message']!r}) = {actual!r}, expected {case['expect']!r}"


def _check_report_result(case, result):
    if case.get("expect") == "err":
        if not _is_fault(result):
            return False, f"expected a Fault, got {result!r}"
        return result["code"] == case["expect_code"], f"err code = {result.get('code')!r}, expected {case['expect_code']!r}"
    if _is_fault(result) or not isinstance(result, dict):
        return False, f"expected an ExceptionReport, got {result!r}"
    if set(result.keys()) != _REPORT_FIELDS:
        return False, f"report keys = {sorted(result.keys())}, expected the ten canonical fields"
    for field in ("environment", "timestamp"):
        if result[field] != case[field]:
            return False, f"{field} = {result[field]!r}, expected the supplied {case[field]!r}"
    if result["severity"] != case["expect_severity"]:
        return False, f"severity = {result['severity']!r}, expected {case['expect_severity']!r}"
    for field in ("message", "exception_type"):
        key = f"expect_{field}"
        if key in case and result[field] != case[key]:
            return False, f"{field} = {result[field]!r}, expected {case[key]!r}"
    return True, f"ok {result!r}"


def _check_jsclassify(case):
    return _check_report_result(case, classify_js_payload(case["payload"], case["environment"], case["timestamp"]))


def _check_pyclassify(case):
    return _check_report_result(case, classify_py_payload(case["payload"], case["environment"], case["timestamp"]))


def _check_normalize(case):
    return _check_report_result(case, normalize(case["source"], case["payload"], case["environment"], case["timestamp"]))


def _check_dedupkey(case):
    result = dedup_key(case["report"])
    return result == case["expect"], f"dedup_key(...) = {result!r}, expected {case['expect']!r}"


def _check_resolve_fault(case):
    """resolve_cadence on an unknown preset name returns the unknown_preset Fault. The success
    arms (a Cadence passing through, a name resolving) carry the Absent encoding and are in laws_he."""
    result = resolve_cadence(case["arg"])
    if not _is_fault(result):
        return False, f"expected a Fault, got {result!r}"
    return result["code"] == case["expect_code"], f"err code = {result.get('code')!r}, expected {case['expect_code']!r}"


_CHECKERS = {
    "vocab": _check_vocab,
    "exports": _check_exports,
    "jsseverity": _check_jsseverity,
    "jsclassify": _check_jsclassify,
    "pyclassify": _check_pyclassify,
    "normalize": _check_normalize,
    "dedupkey": _check_dedupkey,
    "resolve_fault": _check_resolve_fault,
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
