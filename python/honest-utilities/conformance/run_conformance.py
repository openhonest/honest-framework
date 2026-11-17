"""honest-utilities conformance runner (the test-of-record).

Each case in suite.json is data: a `coerce` case feeds a raw string to one of the
six coercers and checks the coerced value, or that the raw string will not coerce
(a fault). Deeper behaviour — the law runner's LawRun arithmetic, resolve_env's
three per-declaration cases and its one-fault aggregation, read_env's environment
boundary, and the key-redaction guarantee — is in laws_hu.py.

No classes, no mocks: every function called is the real honest_utilities function,
and a fault is recognized by its own shape (it carries a "code"), the bare-union
model, never an ok/err envelope.

  uv run --package honest-utilities python honest-utilities/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_utilities import (
    coerce_bool,
    coerce_float,
    coerce_int,
    coerce_key,
    coerce_str,
    coerce_uuid,
)

_COERCERS = {
    "str": coerce_str,
    "int": coerce_int,
    "bool": coerce_bool,
    "float": coerce_float,
    "UUID": coerce_uuid,
    "key": coerce_key,
}


def _is_fault(value):
    """A fault is recognized by its shape: a record carrying a code (section 2.2
    of honest-type). A coerced value never does."""
    return isinstance(value, dict) and "code" in value


def _check_coerce(case):
    spec = case["coerce"]
    got = _COERCERS[spec["type"]](spec["raw"])
    if case["expect"] == "fault":
        return _is_fault(got), f"expected a fault for {spec['type']} {spec['raw']!r}, got {got!r}"
    if _is_fault(got):
        return False, f"expected ok for {spec['type']} {spec['raw']!r}, got fault {got!r}"
    if "expect_value" in case:
        return got == case["expect_value"], f"got {got!r}, expected {case['expect_value']!r}"
    return True, ""


_CHECKERS = {"coerce": _check_coerce}


def _kind(case):
    for name in _CHECKERS:
        if name in case:
            return name
    raise KeyError(f"case {case.get('id')!r} has no known kind")


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
    import laws_hu

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hu.run()
    raise SystemExit(suite_status or laws_status)
