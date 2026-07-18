"""honest-design conformance runner: the reader folds .hd source to IR.

Each behavioural case reads a `.hd` snippet and checks the result (ok with a Document, or a fault
code). The exact-IR pinning and every branch live in laws_hd.py; value cases are checked centrally
by value-check.py.

  uv run --package honest-design python honest-design/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_design import read_hd


def _check_read(case):
    result = read_hd(case["read"]["source"])
    if case["expect"] == "ok":
        matched = "ok" in result
        if "expect_doc" in case:
            matched = matched and result.get("ok") == case["expect_doc"]
        return matched, f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


_CHECKERS = {"read": _check_read}


def _kind(case):
    for kind in _CHECKERS:
        if kind in case:
            return kind
    return "read"


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        if "value_case" in case:
            continue  # value cases are checked centrally by value-check.py
        ok_, detail = _CHECKERS[_kind(case)](case)
        if ok_:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{_kind(case)}]: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_hd

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hd.run()
    raise SystemExit(suite_status or laws_status)
