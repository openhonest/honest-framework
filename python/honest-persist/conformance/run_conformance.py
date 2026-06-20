"""honest-persist conformance runner (section 5.1 - schema diff).

Each case is data: {current, target, expect_operations}. The runner runs diff() and checks the
operations it produces - their op type, table, and any asserted detail keys - in order. No
per-case hand-coded tests.

  uv run --package honest-persist python honest-persist/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_persist import (
    apply,
    check_holds,
    diff,
    parse_check,
    reconstruction_sql,
    requires_reconstruction,
    to_sql,
    validate_schema,
)


def _check_check(case):
    result = parse_check(case["check_expression"])
    if case.get("expect_uncompilable"):
        return "err" in result and result["err"]["code"] == "uncompilable_check", f"got {result}"
    if "err" in result:
        return False, f"unexpected fault {result['err']}"
    holds = check_holds(result["ok"], case["row"])
    return holds == case["expect_holds"], f"got holds={holds}"


class _FakeConn:
    """Records the SQL apply() executes and any sync push pause/resume (the boundary's
    collaborators). Test fixture - the runner is not linted."""

    def __init__(self):
        self.executed = []
        self.paused = 0
        self.resumed = 0

    def execute(self, sql):
        self.executed.append(sql)

    def pause_push(self):
        self.paused += 1

    def resume_push(self):
        self.resumed += 1


def _check_to_sql(case):
    sql = to_sql(case["to_sql"], case["dialect"])
    return sql == case["expect_sql"], f"got {sql!r}"


def _check_apply(case):
    spec = case["apply"]
    result = diff(spec["current"], spec["target"])
    conn = _FakeConn()
    applied = apply(result, spec["target"], conn, case["dialect"])
    ok = applied["success"] == case["expect_success"]
    if "expect_applied" in case:
        ok = ok and applied["operations_applied"] == case["expect_applied"]
    joined = " ; ".join(conn.executed)
    for needle in case.get("expect_executed_contains", []):
        ok = ok and needle in joined
    for needle in case.get("expect_executed_excludes", []):
        ok = ok and needle not in joined
    if case.get("expect_push_paused"):
        ok = ok and conn.paused >= 1 and conn.resumed >= 1
    return ok, f"got {applied} executed={conn.executed}"


def _check_requires(case):
    got = requires_reconstruction(case["reconstruct_op"], case["dialect"])
    return got == case["expect"], f"got {got}"


def _check_reconstruction_sql(case):
    spec = case["reconstruct_sql"]
    statements = reconstruction_sql(spec["table"], spec["target_table"], spec["common_columns"], case["dialect"])
    joined = " ; ".join(statements)
    ok = all(needle in joined for needle in case.get("expect_contains", []))
    return ok, f"got {statements}"


def _check_validate(case):
    result = validate_schema(case["validate"])
    if case["expect"] == "ok":
        return "ok" in result, f"got {result}"
    ok = "err" in result and result["err"]["code"] == "schema_invalid"
    if "expect_error_contains" in case and "err" in result:
        joined = " ".join(result["err"]["detail"]["errors"])
        ok = ok and case["expect_error_contains"] in joined
    return ok, f"got {result}"


def _check_diff(case):
    result = diff(case["current"], case["target"], case.get("decisions"))
    if "expect_fault" in case:
        return "err" in result and result["err"]["code"] == case["expect_fault"], f"got {result.get('err')}"
    if "err" in result:
        return False, f"unexpected fault {result['err']['code']}"
    ok = True
    if "expect_operations" in case:
        ops = result["operations"]
        expected = case["expect_operations"]
        ok = ok and len(ops) == len(expected) and len(result["execution_order"]) == len(ops)
        for got, want in zip(ops, expected):
            ok = ok and got["op"] == want["op"] and got["table"] == want["table"]
            for key, value in want.get("details", {}).items():
                ok = ok and got["details"].get(key) == value
    if "expect_ambiguities" in case:
        ambiguities = result["ambiguities"]
        ok = ok and len(ambiguities) == case["expect_ambiguities"]
        if "expect_confidence" in case and ambiguities:
            ok = ok and ambiguities[0]["confidence"] == case["expect_confidence"]
    return ok, f"ops={[(o['op'], o['table']) for o in result['operations']]} ambiguities={result['ambiguities']}"


_CHECKERS = {
    "diff": _check_diff,
    "to_sql": _check_to_sql,
    "apply": _check_apply,
    "validate": _check_validate,
    "reconstruct_op": _check_requires,
    "reconstruct_sql": _check_reconstruction_sql,
    "check": _check_check,
}


def _kind(case):
    if "check_expression" in case:
        return "check"
    if "reconstruct_op" in case:
        return "reconstruct_op"
    if "reconstruct_sql" in case:
        return "reconstruct_sql"
    if "validate" in case:
        return "validate"
    if "to_sql" in case:
        return "to_sql"
    if "apply" in case:
        return "apply"
    return "diff"


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
    import laws_hp

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hp.run()
    raise SystemExit(suite_status or laws_status)
