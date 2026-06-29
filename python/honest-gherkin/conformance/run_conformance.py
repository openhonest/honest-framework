"""honest-gherkin conformance runner (sections 2-3, unit 1).

Each case is data: a `parse` case feeds source text to parse_feature and checks the resulting
Feature IR (or the bad_feature_syntax fault). Deeper structural checks (tags, And/But resolved
kind, the line-kind classification order) are in laws_hg.py.

  uv run --package honest-gherkin python honest-gherkin/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

import honest_gherkin
from honest_gherkin import (
    compile_pattern,
    empty_registry,
    fold_feature_report,
    match_step,
    parse_feature,
    register_step,
    step_fault,
)


def _check_compile(case):
    spec = case["compile"]
    result = compile_pattern(spec["pattern"])
    if case["expect"] == "ok":
        return "ok" in result and result["ok"]["captures"] == case["expect_captures"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


def _check_match(case):
    spec = case["match"]
    registry = empty_registry()
    for pattern in spec["patterns"]:
        registry = register_step(registry, pattern["kind"], pattern["pattern"], pattern["handler"])
    step = {"kind": "given", "resolved_kind": "given", "text": spec["step_text"], "source_line": 1}
    result = match_step(step, registry)
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


def _check_fold(case):
    spec = case["fold"]
    feature = {"name": spec["feature_name"], "description": "", "scenarios": [], "background_steps": [], "source_path": spec["source_path"]}
    reports = [{"name": f"s{i}", "status": status, "step_results": [], "duration_ms": 0} for i, status in enumerate(spec["scenario_statuses"])]
    report = fold_feature_report(feature, reports)
    ok = (
        report["total_passed"] == case["expect_passed"]
        and report["total_failed"] == case["expect_failed"]
        and report["feature_name"] == spec["feature_name"]
        and report["source_path"] == spec["source_path"]
        and len(report["scenarios"]) == len(reports)
    )
    return ok, f"got {report}"


def _check_vocab(case):
    """A bounded vocabulary (sections 2.1, 7) is exactly the closed set the spec names: the attribute
    on the package must equal the expected members, frozen. Catches any member dropped, emptied, or
    drifted from its named constant, and the whole set going missing."""
    actual = getattr(honest_gherkin, case["vocab"], None)
    expect = frozenset(case["expect_members"])
    return actual == expect, f"{case['vocab']} = {actual!r}, expected {expect!r}"


def _check_failurereport(case):
    """A parse failure is surfaced as a failing FeatureReport (section 8), never swallowed: one errored
    scenario carrying the bad_feature_syntax fault. The full structure is fixed by (path, fault), so
    assert it exactly — every key, status string, the synthetic step, and the 0/1 counts."""
    from honest_gherkin.cli import _parse_failure_report

    spec = case["failurereport"]
    fault = step_fault(spec["code"], spec["detail"], spec.get("scenario_name", ""), spec.get("step_text", ""))
    result = _parse_failure_report(spec["path"], fault)
    return result == case["expect"], f"got {result!r}"


def _check_exports(case):
    """The package's public surface (section 1) is exactly __all__: the listed names, no more and no
    fewer, and every one resolvable as a real attribute. Catches a name emptied or dropped from
    __all__, the whole __all__ removed, and a re-export import deleted."""
    names = getattr(honest_gherkin, "__all__", None)
    if names is None:
        return False, "__all__ is missing"
    expect = case["expect_names"]
    if sorted(names) != sorted(expect):
        return False, f"__all__ = {sorted(names)}, expected {sorted(expect)}"
    missing = [n for n in names if not hasattr(honest_gherkin, n)]
    return not missing, f"__all__ names not importable: {missing}"


def _check_stepfault(case):
    """step_fault (section 7) carries a fault as data: the exact four-key StepFault dict, never raised.
    Catches any key renamed/emptied, any field swapped, and the field order of arguments."""
    spec = case["stepfault"]
    result = step_fault(spec["code"], spec["detail"], spec.get("scenario_name", ""), spec.get("step_text", ""))
    return result == case["expect"], f"got {result!r}"


_CHECKERS = {
    "parse": _check_parse,
    "compile": _check_compile,
    "match": _check_match,
    "fold": _check_fold,
    "vocab": _check_vocab,
    "stepfault": _check_stepfault,
    "exports": _check_exports,
    "failurereport": _check_failurereport,
}


def _kind(case):
    for name in ("compile", "match", "fold", "vocab", "stepfault", "exports", "failurereport"):
        if name in case:
            return name
    return "parse"


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
    import laws_hg

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hg.run()
    raise SystemExit(suite_status or laws_status)
