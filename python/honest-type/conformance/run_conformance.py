"""honest-type conformance runner (sections 2, 3 — unit 1).

Each case is data: a set of declarations and whether building the vocabulary should
succeed or raise. The runner builds the vocabulary and checks. No per-case hand-coded
tests; the cases are the test-of-record. classify() cases are added with unit 2.

  uv run --package honest-type python honest-type/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_type import VocabularyError, vocabulary


def _build(declarations):
    try:
        vocabulary({name: set(members) for name, members in declarations.items()})
        return "ok", ""
    except VocabularyError as exc:
        return "error", str(exc)


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        result, message = _build(case["declarations"])
        ok = result == case["expect"] and case.get("error_contains", "") in message
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']}: expected {case['expect']}, got {result} ({message[:50]})")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    default = str(Path(__file__).parent / "suite.json")
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else default))
