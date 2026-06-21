"""honest-observe conformance runner (sections 2, 6).

Each case is data: a `build_event` case (envelope assembly/validation) or a `matches` case
(projection filtering). The fold-based projection behaviour, which a data file cannot express,
is in laws_ho.py.

  uv run --package honest-observe python honest-observe/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_observe import build_event, matches


def _check_build_event(case):
    spec = case["build_event"]
    result = build_event(**spec["args"])
    if case["expect"] == "ok":
        return "ok" in result and result["ok"] == case["expect_event"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


def _check_matches(case):
    spec = case["matches"]
    got = matches(spec["event"], **spec.get("filters", {}))
    return got == case["expect"], f"got {got}"


_CHECKERS = {
    "build_event": _check_build_event,
    "matches": _check_matches,
}


def _kind(case):
    if "build_event" in case:
        return "build_event"
    return "matches"


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
    import laws_ho

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_ho.run()
    raise SystemExit(suite_status or laws_status)
