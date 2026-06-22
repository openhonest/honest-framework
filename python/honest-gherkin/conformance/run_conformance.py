"""honest-gherkin conformance runner (sections 2-3, unit 1).

Each case is data: a `parse` case feeds source text to parse_feature and checks the resulting
Feature IR (or the bad_feature_syntax fault). Deeper structural checks (tags, And/But resolved
kind, the line-kind classification order) are in laws_hg.py.

  uv run --package honest-gherkin python honest-gherkin/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_gherkin import compile_pattern, parse_feature


def _check_compile(case):
    spec = case["compile"]
    result = compile_pattern(spec["pattern"])
    if case["expect"] == "ok":
        return "ok" in result and result["ok"]["captures"] == case["expect_captures"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


def _check_parse(case):
    spec = case["parse"]
    result = parse_feature(spec["source"], spec["path"])
    if case["expect"] == "ok":
        if "ok" not in result:
            return False, f"expected ok, got {result}"
        feature = result["ok"]
        ok = (
            feature["name"] == case["expect_feature_name"]
            and len(feature["scenarios"]) == case["expect_scenarios"]
            and (not feature["scenarios"] or len(feature["scenarios"][0]["steps"]) == case["expect_first_steps"])
        )
        return ok, f"got {feature}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


_CHECKERS = {"parse": _check_parse, "compile": _check_compile}


def _kind(case):
    return "compile" if "compile" in case else "parse"


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
    import laws_hg

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hg.run()
    raise SystemExit(suite_status or laws_status)
