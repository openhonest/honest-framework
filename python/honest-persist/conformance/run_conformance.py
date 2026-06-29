"""honest-persist conformance runner (section 5.1 - schema diff).

Each case is data: {current, target, expect_operations}. The runner runs diff() and checks the
operations it produces - their op type, table, and any asserted detail keys - in order. No
per-case hand-coded tests.

  uv run --package honest-persist python honest-persist/conformance/run_conformance.py
"""

import asyncio
import json
import sys
from pathlib import Path

import honest_persist
from honest_persist import (
    apply,
    check_holds,
    checked_delete,
    checked_insert,
    checked_select,
    checked_update,
    delete,
    diff,
    execute,
    execute_many,
    execute_one,
    execute_scalar,
    insert,
    parse_check,
    raw,
    reconstruction_sql,
    requires_reconstruction,
    select,
    to_sql,
    transaction,
    update,
    validate_schema,
)

_BUILDERS = {"select": select, "insert": insert, "update": update, "delete": delete, "raw": raw}
_CHECKED_BUILDERS = {
    "checked_select": checked_select,
    "checked_insert": checked_insert,
    "checked_update": checked_update,
    "checked_delete": checked_delete,
}


def _check_query(case):
    spec = case["query"]
    result = _BUILDERS[spec["builder"]](**spec["args"])
    ok = result["sql"] == case["expect_sql"] and result["params"] == case["expect_params"]
    return ok, f"got {result}"


def _check_checked_query(case):
    spec = case["checked_query"]
    result = _CHECKED_BUILDERS[spec["builder"]](**spec["args"])
    if case["expect"] == "ok":
        ok = "ok" in result and result["ok"]["sql"] == case["expect_sql"] and result["ok"]["params"] == case["expect_params"]
        return ok, f"got {result}"
    ok = "err" in result and result["err"]["code"] == case["expect_code"]
    return ok, f"got {result}"


_EXEC_FNS = {"execute": execute, "execute_one": execute_one, "execute_scalar": execute_scalar, "execute_many": execute_many}


class _RowsConn:
    """A stand-in async connection (section 7.4): awaits to canned rows/rowcount for any query
    and records the (sql, params) it was given. Test fixture - conformance is not linted."""

    def __init__(self, rows, rowcount):
        self.rows = rows
        self.rowcount = rowcount
        self.calls = []

    async def execute(self, sql, params):
        self.calls.append((sql, params))
        return {"rows": self.rows, "rowcount": self.rowcount}


def _check_execute(case):
    spec = case["execute"]
    conn = _RowsConn(spec.get("rows", []), spec.get("rowcount", 0))
    result = asyncio.run(_EXEC_FNS[spec["fn"]](spec["query"], conn))
    return result == case["expect"], f"got {result}"


class _TxConn:
    """A stand-in async transactional connection (section 7.5): records begin/commit/rollback
    and each write, raising on the write at `fail_at`. Fixture - conformance is not linted."""

    def __init__(self, fail_at):
        self.fail_at = fail_at
        self.log = []
        self._i = 0

    async def begin(self):
        self.log.append("begin")

    async def commit(self):
        self.log.append("commit")

    async def rollback(self):
        self.log.append("rollback")

    async def execute(self, sql, params):
        index = self._i
        self._i += 1
        self.log.append(("execute", sql))
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("simulated write failure")
        return {"rows": [], "rowcount": 1}


def _check_transaction(case):
    spec = case["transaction"]
    conn = _TxConn(spec.get("fail_at"))
    result = asyncio.run(transaction(spec["writes"], conn))
    if case["expect"] == "ok":
        ok = "ok" in result and result["ok"]["results"] == case["expect_results"] and conn.log[-1] == "commit"
        return ok, f"got {result} log={conn.log}"
    ok = (
        "err" in result
        and result["err"]["code"] == case["expect_code"]
        and result["err"]["detail"]["failed_at"] == case["expect_failed_at"]
        and conn.log[-1] == "rollback"
    )
    return ok, f"got {result} log={conn.log}"


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
    async collaborators). Test fixture - the runner is not linted."""

    def __init__(self):
        self.executed = []
        self.paused = 0
        self.resumed = 0

    async def execute(self, sql):
        self.executed.append(sql)

    async def pause_push(self):
        self.paused += 1

    async def resume_push(self):
        self.resumed += 1

    async def begin(self):
        self.executed.append("BEGIN")

    async def commit(self):
        self.executed.append("COMMIT")

    async def rollback(self):
        self.executed.append("ROLLBACK")

    async def disable_foreign_keys(self):
        self.executed.append("DISABLE FK")

    async def enable_foreign_keys(self):
        self.executed.append("ENABLE FK")

    async def verify_foreign_keys(self):
        self.executed.append("VERIFY FK")
        return []


def _check_to_sql(case):
    sql = to_sql(case["to_sql"], case["dialect"])
    return sql == case["expect_sql"], f"got {sql!r}"


def _check_apply(case):
    spec = case["apply"]
    result = diff(spec["current"], spec["target"])
    conn = _FakeConn()
    applied = asyncio.run(apply(result, spec["target"], conn, case["dialect"]))
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
    statements = reconstruction_sql(spec["table"], spec["target_table"], spec["common_columns"], case["dialect"], temp_name=spec.get("temp_name"))
    if "expect_statements" in case:
        return statements == case["expect_statements"], f"got {statements}"
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
        if "err" not in result or result["err"]["code"] != case["expect_fault"]:
            return False, f"got {result.get('err')}"
        if "expect_fault_message" in case and result["err"].get("message") != case["expect_fault_message"]:
            return False, f"fault message: {result['err'].get('message')!r}"
        if "expect_fault_category" in case and result["err"].get("category") != case["expect_fault_category"]:
            return False, f"fault category: {result['err'].get('category')!r}"
        if "expect_fault_detail" in case and result["err"].get("detail") != case["expect_fault_detail"]:
            return False, f"fault detail: {result['err'].get('detail')!r}"
        return True, ""
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


def _check_exports(case):
    """The package's public surface (section 1) is exactly __all__: the listed names, no more and no
    fewer, and every one resolvable as a real attribute. Catches a name emptied or dropped from
    __all__, the whole __all__ removed, and a re-export import deleted."""
    names = getattr(honest_persist, "__all__", None)
    if names is None:
        return False, "__all__ is missing"
    expect = case["expect_names"]
    if sorted(names) != sorted(expect):
        return False, f"__all__ differs: {sorted(set(names) ^ set(expect))}"
    missing = [n for n in names if not hasattr(honest_persist, n)]
    return not missing, f"__all__ names not importable: {missing}"


_CHECKERS = {
    "exports": _check_exports,
    "diff": _check_diff,
    "to_sql": _check_to_sql,
    "apply": _check_apply,
    "validate": _check_validate,
    "reconstruct_op": _check_requires,
    "reconstruct_sql": _check_reconstruction_sql,
    "check": _check_check,
    "query": _check_query,
    "checked_query": _check_checked_query,
    "execute": _check_execute,
    "transaction": _check_transaction,
}


def _kind(case):
    if "exports" in case:
        return "exports"
    if "checked_query" in case:
        return "checked_query"
    if "execute" in case:
        return "execute"
    if "transaction" in case:
        return "transaction"
    if "query" in case:
        return "query"
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
    import laws_hp

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hp.run()
    raise SystemExit(suite_status or laws_status)
