"""honest-type conformance runner (sections 2, 3, 6, 9 — units 1-2).

Each case is data. Two kinds:
  - construction: {declarations, expect: ok|error, error_contains?} — vocabulary() contract.
  - classify:     {declarations, binding?, tokens, expect_manifest?, expect_rejections?,
                   expect_fault?} — classify() contract (set recognizers only; predicate /
                   insensitive / non-string cases need non-JSON inputs and are verified
                   separately).
The runner builds the objects from the data and checks; no per-case hand-coded tests.

  uv run --package honest-type python honest-type/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_type import VocabularyError, binding, classify, vocabulary


def _check_construction(case):
    try:
        vocabulary({name: set(members) for name, members in case["declarations"].items()})
        result, message = "ok", ""
    except VocabularyError as exc:
        result, message = "error", str(exc)
    ok = result == case["expect"] and case.get("error_contains", "") in message
    return ok, f"got {result} ({message[:50]})"


def _check_classify(case):
    vocab = vocabulary({name: set(members) for name, members in case["declarations"].items()})
    bind = binding(case["binding"]) if "binding" in case else None
    result = classify(case["tokens"], vocab, bind)
    if "expect_fault" in case:
        ok = "err" in result and result["err"]["code"] == case["expect_fault"]
        return ok, f"got {result}"
    reasons = [r["reason"] for r in result.get("_rejections", [])]
    manifest_ok = all(result.get(slot) == value for slot, value in case.get("expect_manifest", {}).items())
    rejections_ok = all(reason in reasons for reason in case.get("expect_rejections", []))
    return manifest_ok and rejections_ok, f"got {result}"


_CHECKERS = {"construction": _check_construction, "classify": _check_classify}


def _kind(case):
    return "classify" if "tokens" in case else "construction"


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
    default = str(Path(__file__).parent / "suite.json")
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else default))
