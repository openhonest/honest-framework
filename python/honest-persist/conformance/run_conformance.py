"""honest-persist conformance runner (section 5.1 - schema diff).

Each case is data: {current, target, expect_operations}. The runner runs diff() and checks the
operations it produces - their op type, table, and any asserted detail keys - in order. No
per-case hand-coded tests.

  uv run --package honest-persist python honest-persist/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_persist import diff


def _check_diff(case):
    result = diff(case["current"], case["target"])
    if "err" in result:
        return False, f"unexpected fault {result['err']['code']}"
    ops = result["operations"]
    expected = case["expect_operations"]
    ok = len(ops) == len(expected) and len(result["execution_order"]) == len(ops)
    for got, want in zip(ops, expected):
        ok = ok and got["op"] == want["op"] and got["table"] == want["table"]
        for key, value in want.get("details", {}).items():
            ok = ok and got["details"].get(key) == value
    summary = [(o["op"], o["table"]) for o in ops]
    return ok, f"got {summary}"


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        ok, detail = _check_diff(case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']}: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    default = str(Path(__file__).parent / "suite.json")
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else default))
