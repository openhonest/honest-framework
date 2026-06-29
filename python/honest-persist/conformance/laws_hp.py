"""honest-persist conformance: the HP laws + DDL/boundary probes (the circle).

The behavioural circle for honest-persist. The HP laws (honest-conformance-suite.md) are
asserted over a generated space of schema pairs: from every (current, target) the diff is
computed, a pure schema-apply model carries `current` through the operations, and the result
is re-diffed against `target`. Convergence (HP-1) and idempotency (HP-2/HP-4) are the
assertion that the re-diff is empty; determinism (HP-3) that the diff is reproducible.

The DDL renderer (to_sql) and the CHECK parser are bounded vocabularies — operation type x
dialect, and the guard DSL's tokens — so they are enumerated exhaustively rather than sampled.
The apply() boundary (reconstruction, sync-push pause, failure handling) is probed with fake
connections. The conformance directory is outside the honest-check gate, so it may model the
apply, build fake connections, and feed deliberately-malformed CHECK strings.
"""

import asyncio
import copy
import io
import sqlite3
from contextlib import redirect_stderr

from honest_test import law, verify_laws

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
from honest_persist.apply import _columns_added
from honest_persist.types import operation

_DIALECTS = ("postgresql", "sqlite", "turso")


# --------------------------------------------------------------------------- schema-apply model


def _apply_ops(schema, operations):
    """A pure model of applying table/column operations to a schema dict — enough to prove
    convergence without a live database. Mirrors what a correct apply() does to the structure."""
    result = copy.deepcopy(schema)
    for op in operations:
        kind, table, details = op["op"], op["table"], op["details"]
        if kind == "create_table":
            result[table] = {"columns": dict(details.get("columns", {}))}
        elif kind == "drop_table":
            result.pop(table, None)
        elif kind == "rename_table":
            result[details["new_name"]] = result.pop(table)
        elif kind == "add_column":
            result[table]["columns"][details["column"]] = dict(details["definition"])
        elif kind == "drop_column":
            result[table]["columns"].pop(details["column"], None)
        elif kind == "rename_column":
            result[table]["columns"][details["to"]] = result[table]["columns"].pop(details["from"])
        elif kind == "alter_column":
            column = result[table]["columns"][details["column"]]
            for field, change in details.get("changes", {}).items():
                column[field] = change["to"]
    return result


_SCHEMAS = {
    "empty": {},
    "users_min": {"users": {"columns": {"id": {"type": "uuid", "nullable": False}, "name": {"type": "text"}}}},
    "users_wide": {"users": {"columns": {"id": {"type": "uuid", "nullable": False}, "email": {"type": "text"}, "age": {"type": "integer"}}}},
    "users_typed": {
        "users": {"columns": {"id": {"type": "text", "nullable": True, "default": "'x'"}}},
        "posts": {"columns": {"id": {"type": "uuid"}}},
    },
}

_PAIRS = [(a, b) for a in _SCHEMAS for b in _SCHEMAS if a != b]


def _hp_convergence(pair):
    current, target = _SCHEMAS[pair[0]], _SCHEMAS[pair[1]]
    result = diff(current, target)
    if "err" in result:
        return [f"diff({pair}) faulted: {result['err']}"]
    reached = _apply_ops(current, result["operations"])
    redo = diff(reached, target)
    if "err" in redo:
        return [f"re-diff after apply faulted: {redo['err']}"]
    if redo["operations"]:
        return [f"not converged: re-diff still has {len(redo['operations'])} ops: {redo['operations']}"]
    return []


def _hp_empty_plan(pair):
    """diff(target, target) is empty — already-conformant means no work (HP-4)."""
    target = _SCHEMAS[pair[1]]
    result = diff(target, target)
    if "err" in result:
        return [f"self-diff faulted: {result['err']}"]
    return [] if not result["operations"] else [f"self-diff produced {result['operations']}"]


def _hp_determinism(pair):
    current, target = _SCHEMAS[pair[0]], _SCHEMAS[pair[1]]
    if diff(current, target) != diff(current, target):
        return [f"diff({pair}) is not deterministic"]
    return []


HP_LAWS = [
    law("HP-1", "applying a diff converges the schema to the target", _hp_convergence),
    law("HP-2/HP-4", "a schema already at target yields an empty plan (idempotency)", _hp_empty_plan),
    law("HP-3", "the diff depends only on (current, target) — it is deterministic", _hp_determinism),
]


# --------------------------------------------------------------------------- render enumeration

_FULL_COLUMNS = {
    "id": {"type": "uuid", "primary_key": True, "nullable": False},
    "name": {"type": "text", "unique": True, "default": "'x'"},
    "flag": {"type": "boolean"},
}

_RENDER_OPS = [
    ("create_table", operation("create_table", "t", {"columns": _FULL_COLUMNS}), "CREATE TABLE"),
    ("drop_table", operation("drop_table", "t", {}), "DROP TABLE"),
    ("rename_table", operation("rename_table", "t", {"new_name": "t2"}), "RENAME TO"),
    ("add_column", operation("add_column", "t", {"column": "c", "definition": {"type": "text"}}), "ADD COLUMN"),
    ("drop_column", operation("drop_column", "t", {"column": "c"}), "DROP COLUMN"),
    ("rename_column", operation("rename_column", "t", {"from": "a", "to": "b"}), "RENAME COLUMN"),
    ("alter_set", operation("alter_column", "t", {"column": "c", "changes": {"type": {"to": "uuid"}, "nullable": {"to": False}, "default": {"to": "'v'"}}}), "ALTER COLUMN"),
    ("alter_drop", operation("alter_column", "t", {"column": "c", "changes": {"nullable": {"to": True}, "default": {"to": None}}}), "DROP NOT NULL"),
    ("add_index", operation("add_index", "t", {"index": "ix", "definition": {"columns": ["a", "b"], "unique": True}}), "UNIQUE INDEX"),
    ("add_index_plain", operation("add_index", "t", {"index": "ix", "definition": {"columns": ["a"]}}), "INDEX"),
    ("drop_index", operation("drop_index", "t", {"index": "ix"}), "DROP INDEX"),
    ("add_foreign_key", operation("add_foreign_key", "t", {"column": "uid", "references": "users.id"}), "FOREIGN KEY"),
    ("drop_foreign_key", operation("drop_foreign_key", "t", {"column": "uid"}), "DROP CONSTRAINT"),
    ("add_constraint", operation("add_constraint", "t", {"constraint": "ck", "definition": {"expression": "age > 0"}}), "CHECK"),
    ("drop_constraint", operation("drop_constraint", "t", {"constraint": "ck"}), "DROP CONSTRAINT"),
]


def _hp_render(subject):
    label, op, keyword = subject
    bad = []
    for dialect in _DIALECTS:
        sql = to_sql(op, dialect)
        if not sql or keyword not in sql:
            bad.append(f"to_sql({label}, {dialect}) = {sql!r}, expected to contain {keyword!r}")
    return bad


RENDER_LAWS = [law("HP-render", "every operation type renders to DDL on every dialect", _hp_render)]


# --------------------------------------------------------------------------- fake connections


class _ReconControl:
    """The transaction + foreign-key control a reconstruction connection must provide (section 5.5):
    begin/commit/rollback and disable/verify foreign keys, each recorded in order so the control flow is
    assertable. verify_foreign_keys reports no violations by default."""

    def _record(self):
        self.calls = []

    async def begin(self):
        self.calls.append("begin")

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def disable_foreign_keys(self):
        self.calls.append("disable_fk")

    async def enable_foreign_keys(self):
        self.calls.append("enable_fk")

    async def verify_foreign_keys(self):
        self.calls.append("verify_fk")
        return []


class _Conn(_ReconControl):
    def __init__(self):
        self.executed = []
        self.paused = 0
        self.resumed = 0
        self._record()

    async def execute(self, sql):
        self.executed.append(sql)

    async def pause_push(self):
        self.paused += 1

    async def resume_push(self):
        self.resumed += 1


class _BareConn(_ReconControl):
    """A connection without sync-push hooks (the hasattr-false path)."""

    def __init__(self):
        self.executed = []
        self._record()

    async def execute(self, sql):
        self.executed.append(sql)


class _FailingConn(_ReconControl):
    def __init__(self, fail_on):
        self.executed = []
        self._fail_on = fail_on
        self.paused = 0
        self.resumed = 0
        self._record()

    async def pause_push(self):
        self.paused += 1

    async def resume_push(self):
        self.resumed += 1

    async def execute(self, sql):
        if self._fail_on in sql:
            raise RuntimeError(f"boom on {self._fail_on}")
        self.executed.append(sql)


class _FkViolationConn(_Conn):
    """A connection whose post-reconstruction foreign-key verification finds a dangling reference."""

    async def verify_foreign_keys(self):
        self.calls.append("verify_fk")
        return [{"table": "child", "column": "parent_id"}]


# --------------------------------------------------------------------------- apply boundary probes

# A column type change forces a table rebuild on sqlite/turso (section 5.5).
_RECON_CURRENT = {"t": {"columns": {"id": {"type": "uuid", "nullable": False}, "keep": {"type": "text"}}}}
_RECON_TARGET = {"t": {"columns": {"id": {"type": "text", "nullable": False}, "keep": {"type": "text"}}, "indexes": {"ix": {"columns": ["keep"]}}}}


def _probe_apply():
    async def _run():
        bad = []
        plan = diff(_RECON_CURRENT, _RECON_TARGET)

        full = _Conn()
        result = await apply(plan, _RECON_TARGET, full, "sqlite")
        joined = " ; ".join(full.executed)
        if not result["success"] or "INSERT INTO" not in joined or "CREATE" not in joined:
            bad.append(f"reconstruction did not copy data / recreate index: {full.executed}")
        # A reconstructed op's own in-place DDL must NOT also run (the post-reconstruction continue skips
        # the to_sql path); the rebuild replaces it.
        if any("ALTER COLUMN" in s for s in full.executed):
            bad.append(f"a reconstructed op must not also execute its in-place DDL: {full.executed}")
        if full.paused < 1 or full.resumed < 1:
            bad.append("reconstruction did not pause/resume sync push")
        # §5.5: foreign-key checks are disabled BEFORE the transaction (the pragma is connection-scoped,
        # not transactional), the rebuild runs, step 6 verifies the foreign keys, the transaction commits,
        # and the foreign-key checks are re-enabled after — the full disable/verify/re-enable lifecycle.
        if full.calls != ["disable_fk", "begin", "verify_fk", "commit", "enable_fk"]:
            bad.append(f"reconstruction control flow should be disable-fk/begin/verify-fk/commit/enable-fk: {full.calls}")

        bare = _BareConn()
        if not (await apply(plan, _RECON_TARGET, bare, "sqlite"))["success"]:
            bad.append("reconstruction failed on a connection without push hooks")

        # §5.5 atomicity: a DDL failure rolls the whole transaction back — never a half-migrated table —
        # and re-enables foreign-key checks so the connection is not left with them off.
        failing = _FailingConn("DROP TABLE")
        failed = await apply(plan, _RECON_TARGET, failing, "sqlite")
        if failed["success"] or "rollback" not in failing.calls or "commit" in failing.calls or "enable_fk" not in failing.calls:
            bad.append(f"a failed reconstruction must roll back and re-enable foreign keys, not commit: {failing.calls}")
        if failing.resumed < 1:
            bad.append("a reconstruction that raises must still resume sync push (the exception path)")

        # §5.5 step 6: a foreign key left dangling after the rebuild rolls back, re-enables, fails with a
        # naming error, and emits a FAILED reconstruct_table migration event.
        fk = _FkViolationConn()
        fk_emitted = []

        async def _fk_emit(event_type, aggregate_type, aggregate_id, payload):
            fk_emitted.append((payload.get("operation"), payload.get("success"), payload.get("fault_code")))
            return {"ok": {}}

        fk_result = await apply(plan, _RECON_TARGET, fk, "sqlite", emit=_fk_emit, db_id="d")
        if fk_result["success"] or "rollback" not in fk.calls or "commit" in fk.calls or "enable_fk" not in fk.calls:
            bad.append(f"a post-reconstruction FK violation must roll back and re-enable foreign keys: {fk.calls}")
        if "foreign keys left dangling after reconstruction" not in (fk_result["error"] or ""):
            bad.append(f"the FK-dangling failure should name its cause: {fk_result['error']}")
        if ("reconstruct_table", False, "reconstruction_failed") not in fk_emitted:
            bad.append(f"a failed reconstruction should emit a failed reconstruct_table event: {fk_emitted}")
        if fk.resumed < 1:
            bad.append("a reconstruction with a dangling foreign key must still resume sync push (the FK path)")

        # Two reconstruction ops on one table reconstruct it ONCE (the already-done skip): exactly one
        # transaction is begun, not one per op.
        two = {"t": {"columns": {"id": {"type": "text"}, "keep": {"type": "integer"}}}}
        plan2 = diff(_RECON_CURRENT, two)
        conn2 = _Conn()
        await apply(plan2, two, conn2, "sqlite")
        if conn2.calls.count("begin") != 1:
            bad.append(f"two reconstruction ops on one table should reconstruct it once: {conn2.calls}")

        # A no-emit apply (emit defaults to None) must produce no migration-event errors on stderr —
        # the emit-None guard short-circuits before touching the (absent) emit.
        no_emit_err = io.StringIO()
        with redirect_stderr(no_emit_err):
            await apply(diff(_RECON_CURRENT, _RECON_TARGET), _RECON_TARGET, _Conn(), "sqlite")
        if no_emit_err.getvalue():
            bad.append(f"a no-emit apply should not touch emit (no stderr): {no_emit_err.getvalue()!r}")

        # An unknown operation has no renderer: apply must report it in full, not silently skip.
        unknown_plan = {"operations": [operation("frobnicate", "t", {})], "execution_order": [0], "ambiguities": [], "dependencies": {}}
        unknown_result = await apply(unknown_plan, {"t": {"columns": {}}}, _Conn(), "postgresql")
        if unknown_result != {"success": False, "executed_sql": [], "operations_applied": 0, "error": "no renderer for 'frobnicate'", "error_operation": 0}:
            bad.append(f"apply on an op with no renderer should report it in full: {unknown_result}")

        # Unresolved ambiguities block apply entirely, with the full result and its error message.
        amb_plan = {"operations": [operation("drop_column", "t", {"column": "c"})], "execution_order": [0], "ambiguities": [{"kind": "x"}], "dependencies": {}}
        amb_result = await apply(amb_plan, {"t": {"columns": {}}}, _Conn(), "postgresql")
        if amb_result != {"success": False, "executed_sql": [], "operations_applied": 0, "error": "unresolved ambiguities; resolve before applying", "error_operation": None}:
            bad.append(f"apply should refuse to run with unresolved ambiguities: {amb_result}")

        # _columns_added: only add_column ops on the named table contribute (so a newly-added column is
        # not copied from the old table during reconstruction).
        added = _columns_added([operation("add_column", "t", {"column": "new"}), operation("add_column", "other", {"column": "x"}), operation("drop_column", "t", {"column": "old"})], "t")
        if added != {"new"}:
            bad.append(f"_columns_added should be only the add_column columns on this table: {added}")

        # The injected emit receives one hf.persist.migration per applied op, keyed by db_id:table.
        emitted = []

        async def _rec_emit(event_type, aggregate_type, aggregate_id, payload):
            emitted.append((event_type, aggregate_type, aggregate_id))
            return {"ok": {}}

        ok_plan = diff({}, {"t": {"columns": {"id": {"type": "text"}}}})
        await apply(ok_plan, {"t": {"columns": {"id": {"type": "text"}}}}, _Conn(), "postgresql", emit=_rec_emit, db_id="db1")
        if emitted != [("hf.persist.migration", "schema", "db1:t")]:
            bad.append(f"apply should emit one hf.persist.migration per op, keyed by db_id:table: {emitted}")

        # A reconstruction emits its own reconstruct_table migration event through the same emit.
        recon_emitted = []

        async def _recon_emit(event_type, aggregate_type, aggregate_id, payload):
            recon_emitted.append((payload.get("operation"), payload.get("sql")))
            return {"ok": {}}

        await apply(diff(_RECON_CURRENT, _RECON_TARGET), _RECON_TARGET, _Conn(), "sqlite", emit=_recon_emit, db_id="db2")
        recon_event = next((sql for op, sql in recon_emitted if op == "reconstruct_table"), None)
        if recon_event is None:
            bad.append(f"a reconstruction should emit a reconstruct_table migration event: {recon_emitted}")
        elif "; " not in recon_event:
            bad.append(f"the reconstruct_table event sql should join its statements with '; ': {recon_event!r}")

        # A failing emit is swallowed — instrumentation must never break a migration — and logs to stderr.
        async def _boom_emit(*args):
            raise RuntimeError("emit down")

        captured = io.StringIO()
        with redirect_stderr(captured):
            swallowed = await apply(ok_plan, {"t": {"columns": {"id": {"type": "text"}}}}, _Conn(), "postgresql", emit=_boom_emit, db_id="db1")
        if not swallowed["success"]:
            bad.append("a failing emit must not break the migration")
        if "migration event emit failed" not in captured.getvalue():
            bad.append(f"a swallowed emit failure should be logged to stderr: {captured.getvalue()!r}")

        # A normal (non-reconstruction) DDL that raises halts apply.
        add_plan = diff({}, {"t": {"columns": {"id": {"type": "text"}}}})
        if (await apply(add_plan, {"t": {"columns": {"id": {"type": "text"}}}}, _FailingConn("CREATE TABLE"), "postgresql"))["success"]:
            bad.append("apply should halt when a DDL statement raises")

        # Unknown op with no renderer also returns None from to_sql directly.
        if to_sql(operation("frobnicate", "t", {}), "sqlite") is not None:
            bad.append("to_sql of an unknown op should be None")

        # reconstruction_sql with no common columns omits the INSERT.
        statements = reconstruction_sql("t", {"columns": {"id": {"type": "text"}}}, [], "sqlite")
        if any("INSERT" in s for s in statements):
            bad.append("reconstruction_sql with no common columns should not INSERT")
        if not requires_reconstruction(operation("alter_column", "t", {}), "sqlite"):
            bad.append("alter_column should require reconstruction on sqlite")
        return bad

    return asyncio.run(_run())


# --------------------------------------------------------------------------- check parser probes


def _probe_check():
    bad = []
    # Each malformed expression exercises one parser failure path -> uncompilable_check.
    malformed = [
        "",                 # empty: no comparison term
        "age >",            # comparison with no right term
        "age IN 5",         # IN without a parenthesised list
        "age IN (b)",       # IN list with a non-literal
        "age IN (1, 2",     # IN list missing close paren
        "(age > 1",         # parenthesised group missing close paren
        "NOT",              # NOT with no clause
        "age > 1 AND",      # junction with no right operand
        "age @ 1",          # unsupported token
    ]
    for expression in malformed:
        result = parse_check(expression)
        if "err" not in result or result["err"]["code"] != "uncompilable_check":
            bad.append(f"parse_check({expression!r}) should be uncompilable: {result}")
    # Every supported comparison operator evaluates (the bounded operator vocabulary).
    operators = {">": (2, 1), "<": (1, 2), ">=": (2, 2), "<=": (2, 2), "=": (1, 1), "!=": (1, 2), "<>": (1, 2)}
    for op, (a, b) in operators.items():
        tree = parse_check(f"x {op} {b}")
        if "ok" not in tree or not check_holds(tree["ok"], {"x": a}):
            bad.append(f"operator {op!r} did not evaluate true for ({a} {op} {b})")
    # AND / OR / NOT / IN, with a string literal and parentheses.
    combos = {
        "x > 0 AND y < 10": {"x": 1, "y": 1, "_": True},
        "x > 5 OR y < 5": {"x": 1, "y": 1, "_": True},
        "NOT x > 5": {"x": 1, "_": True},
        "x IN (1, 2, 3)": {"x": 2, "_": True},
        "name = 'ok'": {"name": "ok", "_": True},
        "(x > 0 OR x < 0) AND x != 0": {"x": 1, "_": True},
    }
    for expression, row in combos.items():
        tree = parse_check(expression)
        if "ok" not in tree or check_holds(tree["ok"], row) is not row["_"]:
            bad.append(f"check {expression!r} did not hold for {row}")
    return bad


def _probe_enforce_checks():
    """CHECK enforcement at the write boundary (§6.2): on a dialect that does not enforce CHECK
    natively, a declared CHECK is compiled and the row validated before the write — never silently
    dropped. table_checks collects column-level and table-level CHECKs; enforce_checks compiles and
    evaluates them; checked_insert refuses a violating row."""
    from honest_persist import checked_insert, dialect_enforces_check, enforce_checks, table_checks

    bad = []

    # Native dialects enforce CHECK in the database; Turso may not, so honest-persist enforces it.
    if not dialect_enforces_check("postgresql") or not dialect_enforces_check("sqlite"):
        bad.append("postgresql and sqlite enforce CHECK natively")
    if dialect_enforces_check("turso"):
        bad.append("turso is not assumed to enforce CHECK natively")

    # table_checks gathers a column-level check and a table-level check constraint, in that order.
    table = {
        "columns": {"price": {"type": "integer", "check": "price > 0"}, "qty": {"type": "integer"}},
        "constraints": {"sane": {"type": "check", "expression": "qty <= 1000"}},
    }
    if table_checks(table) != ["price > 0", "qty <= 1000"]:
        bad.append(f"table_checks should collect column then table CHECKs: {table_checks(table)}")

    schema = {"products": table}
    # Non-native dialect: a satisfying row passes; a violating row is a check_violation fault.
    if "ok" not in enforce_checks(schema, "products", {"price": 5, "qty": 10}, "turso"):
        bad.append("a row satisfying every CHECK should pass enforcement")
    violation = enforce_checks(schema, "products", {"price": 0, "qty": 10}, "turso")
    if violation.get("err", {}).get("code") != "check_violation" or violation["err"]["category"] != "client":
        bad.append(f"a row violating a CHECK should be a client check_violation: {violation}")

    # Native dialect: the database enforces, so the pure layer trusts it (no row evaluation).
    if "ok" not in enforce_checks(schema, "products", {"price": 0, "qty": 10}, "postgresql"):
        bad.append("on a native dialect enforce_checks trusts the database")

    # An uncompilable CHECK on a non-native dialect is a fault (neither natively enforced nor compiled).
    bad_schema = {"t": {"columns": {"x": {"type": "integer", "check": "x @ 1"}}}}
    uncompilable = enforce_checks(bad_schema, "t", {"x": 1}, "turso")
    if uncompilable.get("err", {}).get("code") != "uncompilable_check":
        bad.append(f"an uncompilable CHECK on a non-native dialect should fault: {uncompilable}")

    # checked_insert wires enforcement: a violating row on a non-native dialect is refused.
    refused = checked_insert(schema, "products", {"price": 0, "qty": 1}, "turso")
    if refused.get("err", {}).get("code") != "check_violation":
        bad.append(f"checked_insert should refuse a CHECK-violating row on a non-native dialect: {refused}")
    accepted = checked_insert(schema, "products", {"price": 5, "qty": 1}, "turso")
    if "ok" not in accepted or "INSERT INTO products" not in accepted["ok"]["sql"]:
        bad.append(f"checked_insert should build the INSERT when the row satisfies every CHECK: {accepted}")
    # Default dialect is native, so existing two-arg callers keep their behaviour.
    if "ok" not in checked_insert(schema, "products", {"price": 0, "qty": 1}):
        bad.append("checked_insert defaults to a native dialect, trusting the database")

    # Construction-time validation (§6.2): a CHECK that can be neither natively enforced nor compiled is
    # a construction-time fault, not a silently dropped guarantee surfaced only at the first write.
    from honest_persist import validate_checks

    uncompilable = {"t": {"columns": {"x": {"type": "integer", "check": "x @@ 1"}}}}
    if "ok" not in validate_checks(uncompilable, "postgresql"):
        bad.append("a native dialect enforces CHECK in the database, so construction does not require compilability")
    if "ok" not in validate_checks(schema, "turso"):
        bad.append("a compilable CHECK on a non-native dialect passes construction")
    rejected = validate_checks(uncompilable, "turso")
    if rejected.get("err", {}).get("code") != "uncompilable_check":
        bad.append(f"an uncompilable CHECK on a non-native dialect must fault at construction: {rejected}")
    return bad


# --------------------------------------------------------------------------- validate / extended probes


def _probe_diff_alter():
    """A column change of each kind in isolation produces alter_column carrying that change."""
    bad = []
    base = {"t": {"columns": {"c": {"type": "uuid", "nullable": True, "default": None}}}}
    cases = {
        "type": {"t": {"columns": {"c": {"type": "text", "nullable": True, "default": None}}}},
        "nullable": {"t": {"columns": {"c": {"type": "uuid", "nullable": False, "default": None}}}},
        "default": {"t": {"columns": {"c": {"type": "uuid", "nullable": True, "default": "'v'"}}}},
    }
    for field, target in cases.items():
        result = diff(base, target)
        alters = [op for op in result["operations"] if op["op"] == "alter_column"]
        if not alters or field not in alters[0]["details"]["changes"]:
            bad.append(f"diff with only a {field} change did not produce that alteration: {result['operations']}")
    # A changed index is dropped and re-added.
    with_ix = {"t": {"columns": {"a": {"type": "text"}, "b": {"type": "text"}}, "indexes": {"ix": {"columns": ["a"]}}}}
    changed_ix = {"t": {"columns": {"a": {"type": "text"}, "b": {"type": "text"}}, "indexes": {"ix": {"columns": ["b"]}}}}
    ops = [op["op"] for op in diff(with_ix, changed_ix)["operations"]]
    if "drop_index" not in ops or "add_index" not in ops:
        bad.append(f"a changed index should be dropped and re-added: {ops}")
    # Adding a column and an index on it: the index must run after the column (same-table
    # dependency). Adding two columns plus an index over both gives the index two predecessors.
    existing = {"t": {"columns": {"x": {"type": "text"}}}}
    grown = {"t": {"columns": {"x": {"type": "text"}, "b": {"type": "text"}, "c": {"type": "text"}}, "indexes": {"ix": {"columns": ["b", "c"]}}}}
    plan = diff(existing, grown)
    order = plan["execution_order"]
    ops_in_order = [plan["operations"][i]["op"] for i in order]
    if ops_in_order[-1] != "add_index":
        bad.append(f"add_index must be ordered after its columns: {ops_in_order}")
    # Mutually-dependent views have no valid execution order -> schema_cycle.
    cyclic = {
        "tables": {"t": {"columns": {"a": {"type": "text"}}}},
        "views": {"v1": {"sql": "x", "depends_on": ["v2"]}, "v2": {"sql": "y", "depends_on": ["v1"]}},
    }
    result = diff({}, cyclic)
    if "err" not in result or result["err"]["code"] != "schema_cycle":
        bad.append(f"a view dependency cycle should fault schema_cycle: {result.get('err') or result.get('operations')}")
    return bad


def _probe_validate():
    bad = []
    invalid = {
        "dangling_fk": {"t": {"columns": {"a": {"type": "text", "references": "ghost.id"}}}},
        "malformed_fk": {"t": {"columns": {"a": {"type": "text", "references": "nodot"}}}},
        "missing_pk": {"t": {"columns": {"a": {"type": "text"}}, "primary_key": ["b"]}},
        "missing_index": {"t": {"columns": {"a": {"type": "text"}}, "indexes": {"ix": {"columns": ["b"]}}}},
        "missing_constraint": {"t": {"columns": {"a": {"type": "text"}}, "constraints": {"ck": {"columns": ["b"]}}}},
    }
    for label, schema in invalid.items():
        result = validate_schema(schema)
        if "err" not in result or result["err"]["code"] != "schema_invalid":
            bad.append(f"validate_schema({label}) should be schema_invalid: {result}")
    # A valid schema with a real PK, index, and constraint validates (the not-missing branches).
    valid = {
        "t": {
            "columns": {"a": {"type": "text"}, "b": {"type": "text"}},
            "primary_key": ["a"],
            "indexes": {"ix": {"columns": ["b"]}},
            "constraints": {"ck": {"columns": ["a"]}},
        }
    }
    if "ok" not in validate_schema(valid):
        bad.append("a schema with valid PK/index/constraint should validate ok")
    # A view depending on a missing table is invalid.
    bad_view = {"tables": {"t": {"columns": {"a": {"type": "text"}}}}, "views": {"v": {"depends_on": ["ghost"]}}}
    if "err" not in validate_schema(bad_view):
        bad.append("a view depending on a missing table should be invalid")
    return bad


def _probe_extended():
    bad = []
    base = {"tables": {"t": {"columns": {"a": {"type": "text"}}}}}
    with_view = {"tables": base["tables"], "views": {"v": {"sql": "SELECT a FROM t", "depends_on": ["t"]}}}
    changed_view = {"tables": base["tables"], "views": {"v": {"sql": "SELECT a, a FROM t", "depends_on": ["t"]}}}
    with_trig = {"tables": base["tables"], "triggers": {"tr": {"table": "t", "sql": "X"}}}
    changed_trig = {"tables": base["tables"], "triggers": {"tr": {"table": "t", "sql": "Y"}}}
    with_func = {"tables": base["tables"], "procedures": {"f": {"kind": "function", "sql": "A"}}}
    changed_func = {"tables": base["tables"], "procedures": {"f": {"kind": "function", "sql": "B"}}}
    with_proc = {"tables": base["tables"], "procedures": {"p": {"kind": "procedure", "sql": "A"}}}
    changed_proc = {"tables": base["tables"], "procedures": {"p": {"kind": "procedure", "sql": "B"}}}

    def _ops(current, target):
        result = diff(current, target)
        return [] if "err" in result else [op["op"] for op in result["operations"]]

    expectations = [
        ("view_add", base, with_view, "create_view"),
        ("view_drop", with_view, base, "drop_view"),
        ("view_change", with_view, changed_view, "create_view"),
        ("trigger_add", base, with_trig, "create_trigger"),
        ("trigger_drop", with_trig, base, "drop_trigger"),
        ("trigger_change", with_trig, changed_trig, "create_trigger"),
        ("function_add", base, with_func, "create_function"),
        ("function_drop", with_func, base, "drop_function"),
        ("function_replace", with_func, changed_func, "replace_function"),
        ("procedure_add", base, with_proc, "create_function"),
        ("procedure_change", with_proc, changed_proc, "drop_function"),
    ]
    for label, current, target, expected_op in expectations:
        ops = _ops(current, target)
        if expected_op not in ops:
            bad.append(f"diff({label}) should emit {expected_op}: got {ops}")

    # A schema diffed against itself yields no operations even when it carries indexes, views,
    # triggers, and functions — the unchanged-common branch of every extended-object diff.
    with_index = {"t": {"columns": {"a": {"type": "text"}}, "indexes": {"ix": {"columns": ["a"]}}}}
    for label, schema in [("index", with_index), ("view", with_view), ("trigger", with_trig), ("function", with_func)]:
        result = diff(schema, schema)
        if "err" in result or result["operations"]:
            bad.append(f"self-diff of a schema with an unchanged {label} should be empty: {result}")
    return bad


def _probe_checked():
    """Schema-checked builders (§7.3): every table and column a query names is validated
    against the declared schema, returning ok(Query) or a typed fault. Pure. Exercises every
    branch."""
    from honest_persist import checked_delete, checked_insert, checked_select, checked_update, select

    bad = []
    schema = {
        "users": {"columns": {"id": {"type": "int"}, "email": {"type": "text"}, "status": {"type": "text"}, "name": {"type": "text"}, "created": {"type": "int"}}},
        "orders": {"columns": {"user_id": {"type": "int"}}},
    }

    # select: ok with wildcard, where, ORDER BY (a '-' descending term), and a known join.
    args = {"columns": ["*"], "where": {"status": "active"}, "order_by": ["name", "-created"], "joins": [{"table": "orders", "on": "orders.user_id = users.id"}]}
    r = checked_select(schema, "users", **args)
    if "ok" not in r:
        bad.append(f"checked_select valid should be ok: {r}")
    elif r["ok"] != select("users", **args):
        bad.append("checked_select ok must wrap exactly the raw select Query")
    # select: ok with no columns/where/order_by/joins (the `or []` empty branches).
    if "ok" not in checked_select(schema, "users"):
        bad.append("checked_select with no optional args should be ok")
    # select: unknown column in each of the three positions, plus unknown table and join table.
    if checked_select(schema, "users", columns=["emial"]).get("err", {}).get("code") != "unknown_column":
        bad.append("misspelled select column should fault unknown_column")
    if checked_select(schema, "users", where={"ghost": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown where column should fault unknown_column")
    if checked_select(schema, "users", order_by=["-ghost"]).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown order_by column should fault unknown_column")
    if checked_select(schema, "ghost").get("err") != {"code": "unknown_table", "message": "Table 'ghost' is not declared in the schema", "category": "server", "detail": {"table": "ghost"}}:
        bad.append(f"an unknown table should fault unknown_table in full: {checked_select(schema, 'ghost')}")
    if checked_select(schema, "users", joins=[{"table": "ghost", "on": "x"}]).get("err") != {"code": "unknown_table", "message": "Join table 'ghost' is not declared in the schema", "category": "server", "detail": {"table": "ghost"}}:
        bad.append(f"an unknown join table should fault unknown_table in full: {checked_select(schema, 'users', joins=[{'table': 'ghost', 'on': 'x'}])}")
    # the unknown_column fault names the offending column(s), the table, and the declared set, with the
    # server category and the full message.
    col_err = checked_select(schema, "users", columns=["emial", "id"]).get("err", {})
    if col_err.get("category") != "server" or col_err.get("message") != "Column(s) ['emial'] not declared on table 'users'":
        bad.append(f"unknown_column fault should carry its message and server category: {col_err}")
    detail = col_err.get("detail", {})
    if detail.get("columns") != ["emial"] or detail.get("table") != "users" or "email" not in detail.get("declared", []):
        bad.append(f"unknown_column detail should name the bad column, table, and declared set: {detail}")

    # insert / update / delete: ok and unknown-column paths; the where=None branch on update and delete.
    if "ok" not in checked_insert(schema, "users", {"id": 1, "email": "a@b.co"}):
        bad.append("valid checked_insert should be ok")
    if checked_insert(schema, "users", {"nope": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown insert column should fault")
    if "ok" not in checked_update(schema, "users", {"status": "active"}, {"id": 1}):
        bad.append("valid checked_update should be ok")
    # a multi-column update joins its SET assignments with ', ' (pins the set_clause separator)
    multi_update = checked_update(schema, "users", {"status": "active", "email": "x"}, {"id": 1})
    if "ok" not in multi_update or multi_update["ok"]["sql"] != "UPDATE users SET status = :set_status, email = :set_email WHERE id = :id":
        bad.append(f"a multi-column update should comma-join its SET assignments: {multi_update}")
    if "ok" not in checked_update(schema, "users", {"status": "active"}, None):
        bad.append("checked_update with where=None should be ok")
    if checked_update(schema, "users", {"nope": 1}, {"id": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown update value column should fault")
    if checked_update(schema, "users", {"status": "x"}, {"ghost": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown update where column should fault")
    if "ok" not in checked_delete(schema, "users", {"id": 1}):
        bad.append("valid checked_delete should be ok")
    if "ok" not in checked_delete(schema, "users", None):
        bad.append("checked_delete with where=None should be ok")
    if checked_delete(schema, "users", {"ghost": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown delete where column should fault")
    # a table declared with no columns -> declared set empty -> any column is unknown.
    if checked_insert({"t": {}}, "t", {"a": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("a table with no declared columns should reject any column")
    return bad


class _RowsConn:
    """A stand-in async connection (§7.4): awaits to canned rows/rowcount and records the
    (sql, params) it was handed. Conformance is not linted, so a fixture class is fine here."""

    def __init__(self, rows, rowcount):
        self.rows = rows
        self.rowcount = rowcount
        self.calls = []

    async def execute(self, sql, params):
        self.calls.append((sql, params))
        return {"rows": self.rows, "rowcount": self.rowcount}


def _probe_execute():
    """Execute (§7.4): the async I/O boundary, exercised with a stand-in connection. Plain data
    out, empty-result branches return None, and the connection is handed the Query's sql +
    params. Driven through one event loop."""
    from honest_persist import execute, execute_many, execute_one, execute_scalar

    async def _run():
        bad = []
        q = {"sql": "SELECT id, name FROM t WHERE id = :id", "params": {"id": 1}}
        full = _RowsConn([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], 2)
        empty = _RowsConn([], 0)

        if await execute(q, full) != [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]:
            bad.append("execute should return every row")
        if await execute(q, empty) != []:
            bad.append("execute on no rows should be []")
        if await execute_one(q, full) != {"id": 1, "name": "a"}:
            bad.append("execute_one should return the first row")
        if await execute_one(q, empty) is not None:
            bad.append("execute_one on no rows should be None")
        if await execute_scalar(q, full) != 1:
            bad.append("execute_scalar should return the first column of the first row")
        if await execute_scalar(q, empty) is not None:
            bad.append("execute_scalar on no rows should be None")
        if await execute_many(q, full) != 2:
            bad.append("execute_many should return the rowcount")
        # the boundary hands the connection exactly the Query's sql and params, nothing rebuilt.
        if full.calls[-1] != ("SELECT id, name FROM t WHERE id = :id", {"id": 1}):
            bad.append(f"execute should pass the Query's sql and params to the connection: {full.calls[-1]}")
        return bad

    return asyncio.run(_run())


class _TxConn:
    """A stand-in async transactional connection (§7.5): records begin/commit/rollback and each
    write, raising on the write at `fail_at`. Conformance is not linted, so a fixture is fine."""

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


def _probe_transaction():
    """Transactions (§7.5): all-or-nothing over a stand-in connection. Commit on success,
    rollback on the first failing write, and the begin/commit/rollback sequence is exact."""
    from honest_persist import transaction

    async def _run():
        bad = []
        w1 = {"sql": "INSERT INTO t (id) VALUES (:id)", "params": {"id": 1}}
        w2 = {"sql": "UPDATE t SET n = :n WHERE id = :id", "params": {"n": 9, "id": 1}}

        # success: every write runs, then commit; results are the per-write rows-affected.
        commit = _TxConn(None)
        r = await transaction([w1, w2], commit)
        if r != {"ok": {"results": [1, 1]}}:
            bad.append(f"committed transaction should return both rows-affected: {r}")
        if commit.log != ["begin", ("execute", w1["sql"]), ("execute", w2["sql"]), "commit"]:
            bad.append(f"commit path sequence wrong: {commit.log}")

        # empty: begin then commit, no writes, empty results.
        empty = _TxConn(None)
        if await transaction([], empty) != {"ok": {"results": []}}:
            bad.append("empty transaction should commit with no results")
        if empty.log != ["begin", "commit"]:
            bad.append(f"empty path sequence wrong: {empty.log}")

        # failure on the first write: rollback, no commit, no second write, failed_at = 0.
        first = _TxConn(0)
        r = await transaction([w1, w2], first)
        err_w = r.get("err", {})
        if err_w.get("code") != "write_failed" or err_w.get("category") != "server" or not err_w.get("message") or err_w.get("detail", {}).get("failed_at") != 0:
            bad.append(f"failure should be a write_failed server fault at index 0 with a message: {r}")
        if first.log != ["begin", ("execute", w1["sql"]), "rollback"]:
            bad.append(f"rollback path should stop at the failing write: {first.log}")

        # failure on a later write: the earlier write ran, then rollback; failed_at points at it.
        middle = _TxConn(1)
        r = await transaction([w1, w2], middle)
        if r["err"]["detail"]["failed_at"] != 1 or middle.log[-1] != "rollback" or "commit" in middle.log:
            bad.append(f"mid-transaction failure should roll back at index 1: {r} log={middle.log}")

        # req 14 (§8): a transaction emits one hf.persist.transaction through the injected emit.
        events = []

        async def rec_emit(event_type, aggregate_type, aggregate_id, payload):
            events.append((event_type, aggregate_type, aggregate_id, payload))

        await transaction([w1, w2], _TxConn(None), rec_emit, "users_db", "req-1")
        if len(events) != 1 or events[0][0] != "hf.persist.transaction" or events[0][1] != "transaction" or events[0][2] != "users_db":
            bad.append(f"a committed transaction should emit one hf.persist.transaction for the db: {events}")
        else:
            payload = events[0][3]
            if payload["write_count"] != 2 or payload["outcome"] != "ok" or payload["failed_at"] is not None or payload["request_id"] != "req-1" or payload["duration_ns"] < 0:
                bad.append(f"committed transaction event payload wrong: {payload}")

        # A failed transaction emits outcome constraint_violation with the failing write's index.
        fail_events = []

        async def rec_fail(event_type, aggregate_type, aggregate_id, payload):
            fail_events.append(payload)

        failed = await transaction([w1, w2], _TxConn(1), rec_fail, "users_db", "req-2")
        if failed.get("err", {}).get("code") != "write_failed":
            bad.append("a failing transaction still returns write_failed")
        if not fail_events or fail_events[0]["outcome"] != "constraint_violation" or fail_events[0]["failed_at"] != 1:
            bad.append(f"a failed transaction should emit constraint_violation with failed_at: {fail_events}")

        # A failing emit is swallowed — the transaction result is unaffected — and logged to stderr.
        async def down_emit(event_type, aggregate_type, aggregate_id, payload):
            raise RuntimeError("emit is down")

        down_err = io.StringIO()
        with redirect_stderr(down_err):
            down_result = await transaction([w1], _TxConn(None), down_emit, "users_db", "req-3")
        if down_result != {"ok": {"results": [1]}}:
            bad.append("a failing transaction-event emit must not break the transaction")
        if "transaction event emit failed" not in down_err.getvalue():
            bad.append(f"a swallowed transaction-emit failure should log to stderr: {down_err.getvalue()!r}")

        # A no-emit transaction (emit defaults to None) touches no emit and writes no stderr.
        no_emit_err = io.StringIO()
        with redirect_stderr(no_emit_err):
            await transaction([w1], _TxConn(None))
        if no_emit_err.getvalue():
            bad.append(f"a no-emit transaction should not touch emit (no stderr): {no_emit_err.getvalue()!r}")
        return bad

    return asyncio.run(_run())


def _probe_instrument():
    """Pool-layer instrumentation (§8.3, 8.5, 8.7, 8.8): the typed pool faults and the pure event
    payload builders persist emits through honest-observe — branch paths a data file leaves implicit."""
    from honest_persist.instrument import (
        POOL_FAULT_CODES,
        build_migration_event,
        build_pool_event,
        build_query_event,
        build_transaction_event,
        extract_table,
        pool_fault,
        sql_hash,
    )

    bad = []
    if POOL_FAULT_CODES != {"unknown_database", "unresolvable_dsn", "unknown_tenant", "pool_exhausted", "pool_closed", "credential_rejected", "lifecycle_failed"}:
        bad.append("POOL_FAULT_CODES vocabulary is wrong")
    # Each fault code maps to its exact category (the full client/server map).
    expected_categories = {"unknown_database": "client", "unknown_tenant": "client", "unresolvable_dsn": "server", "pool_exhausted": "server", "pool_closed": "server", "credential_rejected": "server", "lifecycle_failed": "server"}
    for code, category in expected_categories.items():
        fault_record = pool_fault(code, "msg")
        if fault_record != {"code": code, "message": "msg", "category": category}:
            bad.append(f"pool_fault({code}) wrong: {fault_record}")
    if extract_table("SELECT * FROM users WHERE id = 1") != "users":
        bad.append("extract_table should find the FROM table")
    if extract_table("INSERT INTO orders (x) VALUES (1)") != "orders":
        bad.append("extract_table should find the INTO table")
    if extract_table("UPDATE accounts SET x = 1") != "accounts":
        bad.append("extract_table should find the UPDATE table")
    if extract_table("BEGIN") != "":
        bad.append("extract_table should return '' when no table is present")
    if sql_hash("SELECT 1") != "e004ebd5b5532a4b85984a62f8ad48a81aa3460c1ca07701f386135d72cdecf5" or sql_hash("SELECT 1") == sql_hash("SELECT 2"):
        bad.append("sql_hash should be a stable per-sql sha256 digest")

    # Each event builder's full payload is pinned exactly (every key and value).
    builders = [
        (build_query_event("db", "users", "select", 3, 1500, "SELECT 1", "r1", None, True),
         {"db_id": "db", "table_name": "users", "operation": "select", "row_count": 3, "duration_ns": 1500, "sql_hash": sql_hash("SELECT 1"), "sql": "SELECT 1", "request_id": "r1", "fault_code": None}),
        (build_query_event("db", "users", "select", 3, 1500, "SELECT 1", "r1", "bad", False),
         {"db_id": "db", "table_name": "users", "operation": "select", "row_count": 3, "duration_ns": 1500, "sql_hash": sql_hash("SELECT 1"), "sql": None, "request_id": "r1", "fault_code": "bad"}),
        (build_migration_event("db", "create_table", "users", {"x": 1}, 2000, "CREATE TABLE users", True, None),
         {"db_id": "db", "operation": "create_table", "table": "users", "detail": {"x": 1}, "duration_ns": 2000, "sql": "CREATE TABLE users", "success": True, "fault_code": None}),
        (build_pool_event("db", "closed", 10, 1, 2, 5000, "pool_closed", "shut"),
         {"db_id": "db", "event": "closed", "pool_size": 10, "active": 1, "waiting": 2, "duration_ns": 5000, "fault_code": "pool_closed", "message": "shut"}),
        (build_transaction_event("db", 3, "constraint_violation", 2, 1200, "r1"),
         {"db_id": "db", "write_count": 3, "outcome": "constraint_violation", "failed_at": 2, "duration_ns": 1200, "request_id": "r1"}),
    ]
    for actual, expected in builders:
        if actual != expected:
            bad.append(f"instrument event builder mismatch: got {actual}, expected {expected}")
    return bad


def _probe_instrumented():
    """Instrumented execute (§8.5): the boundary emits hf.persist.query through the injected emit on
    success and on failure (then re-raises), never blocks the result, swallows emit failures, and
    skips instrumentation entirely when no emit is wired in (zero overhead when disabled)."""
    from honest_persist.instrumented import instrumented_execute

    async def _run():
        bad = []
        q = {"sql": "SELECT id FROM users WHERE id = :id", "params": {"id": 1}}
        conn = _RowsConn([{"id": 1}, {"id": 2}], 2)

        # No emit wired in: run and return the rows, no event, and no stderr (the emit-None fast path
        # never touches the absent emit).
        no_emit_err = io.StringIO()
        with redirect_stderr(no_emit_err):
            no_emit_rows = await instrumented_execute(q, conn, None, "users_db", "select", "r1", True)
        if no_emit_rows != [{"id": 1}, {"id": 2}]:
            bad.append("with no emit, instrumented_execute should just return the rows")
        if no_emit_err.getvalue():
            bad.append(f"a no-emit instrumented_execute should not touch emit (no stderr): {no_emit_err.getvalue()!r}")

        # A failing emit is swallowed and logged to stderr; the query result is unaffected.
        async def down_emit(event_type, aggregate_type, aggregate_id, payload):
            raise RuntimeError("emit is down")

        down_err = io.StringIO()
        with redirect_stderr(down_err):
            down_rows = await instrumented_execute(q, conn, down_emit, "users_db", "select", "r1", True)
        if down_rows != [{"id": 1}, {"id": 2}] or "query event emit failed" not in down_err.getvalue():
            bad.append(f"a failing query-event emit should be swallowed and logged: {down_rows}, {down_err.getvalue()!r}")

        # Success: one hf.persist.query event, keyed db:table, fault_code null, row_count set.
        calls = []

        async def emit(event_type, aggregate_type, aggregate_id, payload):
            calls.append((event_type, aggregate_type, aggregate_id, payload))
            return {"ok": {"event_id": "e"}}

        if await instrumented_execute(q, conn, emit, "users_db", "select", "r1", True) != [{"id": 1}, {"id": 2}]:
            bad.append("instrumented_execute should still return the rows")
        if len(calls) != 1 or calls[0][:3] != ("hf.persist.query", "persist", "users_db:users"):
            bad.append(f"a successful query should emit one hf.persist.query keyed db:table: {calls}")
        elif calls[0][3]["fault_code"] is not None or calls[0][3]["row_count"] != 2 or calls[0][3]["operation"] != "select":
            bad.append(f"the success event payload is wrong: {calls[0][3]}")

        # Query failure: emit the event with a fault code (and no full sql outside development), re-raise.
        failures = []

        async def emit_fail(event_type, aggregate_type, aggregate_id, payload):
            failures.append(payload)

        raised = False
        try:
            await instrumented_execute(q, _TxConn(fail_at=0), emit_fail, "users_db", "select", "r1", False)
        except RuntimeError:
            raised = True
        if not raised:
            bad.append("a query failure should re-raise after emitting")
        if len(failures) != 1 or failures[0]["fault_code"] is None or failures[0]["row_count"] != 0 or failures[0]["sql"] is not None:
            bad.append(f"a failed non-development query should emit fault_code, row_count 0, no full sql: {failures}")

        # A failing emit is swallowed: the query result is unaffected.
        async def emit_down(event_type, aggregate_type, aggregate_id, payload):
            raise ValueError("emit is down")

        if await instrumented_execute(q, conn, emit_down, "users_db", "select", "r1", True) != [{"id": 1}, {"id": 2}]:
            bad.append("a failing emit must never break the query")
        return bad

    return asyncio.run(_run())


def _probe_instrumented_apply():
    """Instrumented apply (§8.7): apply emits one hf.persist.migration per operation executed, in
    execution order, through the injected emit (schema aggregate, db:table id); a failed operation
    emits with the fault code; a reconstructed table emits one reconstruct_table event; a failing
    emit is swallowed."""

    async def _run():
        bad = []
        target = {"a": {"columns": {"id": {"type": "integer"}}}, "b": {"columns": {"id": {"type": "integer"}}}}
        plan = diff({}, target)

        # Two plain DDL operations -> one migration event per op.
        events = []

        async def emit(event_type, aggregate_type, aggregate_id, payload):
            events.append((event_type, aggregate_type, aggregate_id, payload))

        result = await apply(plan, target, _Conn(), "postgresql", emit, "users_db")
        if not result["success"]:
            bad.append("the plain apply should succeed")
        if len(events) != 2 or any(e[0] != "hf.persist.migration" or e[1] != "schema" for e in events):
            bad.append(f"apply should emit one hf.persist.migration per operation: {events}")
        elif events[0][3]["success"] is not True or events[0][3]["fault_code"] is not None or events[0][3]["operation"] != "create_table":
            bad.append(f"the migration event payload is wrong: {events[0][3]}")

        # A failing DDL emits one event with the fault code, then apply halts.
        fail_events = []

        async def emit_fail(event_type, aggregate_type, aggregate_id, payload):
            fail_events.append(payload)

        one = {"a": {"columns": {"id": {"type": "integer"}}}}
        fresult = await apply(diff({}, one), one, _FailingConn("CREATE TABLE"), "postgresql", emit_fail, "users_db")
        if fresult["success"]:
            bad.append("apply should halt on a failing DDL")
        if len(fail_events) != 1 or fail_events[0]["success"] is not False or fail_events[0]["fault_code"] is None:
            bad.append(f"a failed operation should emit success False with a fault code: {fail_events}")

        # A reconstructed table emits one reconstruct_table event (success), and a failed
        # reconstruction emits one with success False.
        recon_events = []

        async def emit_recon(event_type, aggregate_type, aggregate_id, payload):
            recon_events.append(payload)

        await apply(diff(_RECON_CURRENT, _RECON_TARGET), _RECON_TARGET, _Conn(), "sqlite", emit_recon, "users_db")
        if not any(p["operation"] == "reconstruct_table" and p["success"] is True for p in recon_events):
            bad.append(f"a reconstructed table should emit a successful reconstruct_table event: {recon_events}")
        recon_fail = []

        async def emit_recon_fail(event_type, aggregate_type, aggregate_id, payload):
            recon_fail.append(payload)

        await apply(diff(_RECON_CURRENT, _RECON_TARGET), _RECON_TARGET, _FailingConn("DROP TABLE"), "sqlite", emit_recon_fail, "users_db")
        if not any(p["operation"] == "reconstruct_table" and p["success"] is False for p in recon_fail):
            bad.append(f"a failed reconstruction should emit a reconstruct_table event with success False: {recon_fail}")

        # A failing emit is swallowed: the migration still succeeds.
        async def emit_down(event_type, aggregate_type, aggregate_id, payload):
            raise ValueError("emit is down")

        if not (await apply(plan, target, _Conn(), "postgresql", emit_down, "users_db"))["success"]:
            bad.append("a failing emit must never break the migration")
        return bad

    return asyncio.run(_run())


def _probe_pool():
    """Pool routing (§8.1, 8.2): resolve a manifest to its pool selector — a db_id selects a
    registered database, a tenant_id a per-tenant one, the credential and lifecycle are carried, and
    a manifest naming no database faults unknown_database."""
    from honest_persist.pool import POOL_LIFECYCLES, resolve_pool_key

    bad = []
    if POOL_LIFECYCLES != {"persistent", "ephemeral", "on_demand"}:
        bad.append("POOL_LIFECYCLES vocabulary is wrong")
    by_db = resolve_pool_key({"db_id": "users_db", "id": 1})
    if "ok" not in by_db or by_db["ok"]["database"] != "users_db" or by_db["ok"]["kind"] != "db_id":
        bad.append(f"a db_id should select a registered database: {by_db}")
    elif by_db["ok"]["lifecycle"] != "persistent" or by_db["ok"]["credential"] is not None:
        bad.append("the default lifecycle is persistent and there is no credential by default")
    by_tenant = resolve_pool_key({"tenant_id": "acme", "credential": "read_replica", "db_lifecycle": "ephemeral"})
    if "ok" not in by_tenant or by_tenant["ok"]["kind"] != "tenant_id" or by_tenant["ok"]["database"] != "acme":
        bad.append(f"a tenant_id should select a per-tenant database: {by_tenant}")
    elif by_tenant["ok"]["credential"] != "read_replica" or by_tenant["ok"]["lifecycle"] != "ephemeral":
        bad.append("the credential and lifecycle should be carried through")
    none = resolve_pool_key({"some": "query data"})
    if none.get("err", {}).get("code") != "unknown_database":
        bad.append(f"a manifest naming no database should fault unknown_database: {none}")
    return bad


class _SqliteConn:
    """A real in-memory SQLite connection adapted to persist's duck-typed boundary (§7.4): await to
    {rows, rowcount}, named params, dict rows. Conformance is not linted, so a fixture class is fine."""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    async def execute(self, sql, params=None):
        cursor = self._conn.execute(sql, params or {})
        return {"rows": [dict(row) for row in cursor.fetchall()], "rowcount": cursor.rowcount}

    def close(self):
        self._conn.close()


def _probe_pool_registry():
    """The pool registry (§8.1): create-on-first-contact, cache, and reuse — the cache threaded as a
    value with an injected connect — exercised end to end against a real in-memory SQLite database."""
    from honest_persist import empty_pool_registry, execute, get_pool, insert, raw, select

    async def _run():
        bad = []
        created = []

        async def connect(selector):
            created.append(selector["database"])
            return _SqliteConn()

        registry = empty_pool_registry()
        if registry != {}:
            bad.append("empty_pool_registry should be an empty cache")

        # First contact creates the pool and caches it.
        result, registry = await get_pool(registry, {"db_id": "main"}, connect, 0)
        if "ok" not in result or created != ["main"]:
            bad.append(f"first contact should create and return a connection: {result}, {created}")
        conn = result["ok"]

        # The same database reuses the cached connection; connect is not called again.
        result2, registry = await get_pool(registry, {"db_id": "main"}, connect, 1)
        if result2["ok"] is not conn or created != ["main"]:
            bad.append(f"a seen database should reuse the cached connection: {created}")

        # A different database, and a different credential variant, are each a new pool.
        _, registry = await get_pool(registry, {"db_id": "other"}, connect, 2)
        _, registry = await get_pool(registry, {"db_id": "main", "credential": "replica"}, connect, 3)
        if created != ["main", "other", "main"]:
            bad.append(f"an unseen database or credential should create a new pool: {created}")

        # A manifest naming no database errs and does not touch the cache.
        errored, unchanged = await get_pool(registry, {"q": 1}, connect, 4)
        if errored.get("err", {}).get("code") != "unknown_database" or unchanged is not registry:
            bad.append(f"a manifest with no database should err and leave the cache: {errored}")

        # End to end against real SQLite: create, insert, and select through the cached connection.
        await execute(raw("CREATE TABLE t (x integer)"), conn)
        await execute(insert("t", {"x": 7}), conn)
        rows = await execute(select("t", ["x"]), conn)
        if rows != [{"x": 7}]:
            bad.append(f"persist should round-trip a row through real SQLite: {rows}")
        return bad

    return asyncio.run(_run())


def _probe_lifecycle():
    """Pool lifecycle execution (§8.2): is_idle is a pure threshold check; reap_idle closes and
    evicts on_demand pools idle past the threshold, leaving persistent and ephemeral pools and
    recently-used on_demand pools alone — closing real SQLite connections through the injected close."""
    from honest_persist import empty_pool_registry, get_pool, is_idle, reap_idle

    ms = 1_000_000  # nanoseconds per millisecond

    async def _run():
        bad = []
        if is_idle(0, 5 * ms, 10) or not is_idle(0, 20 * ms, 10):
            bad.append("is_idle should be true only once the idle time exceeds the threshold")

        closed = []

        async def close(conn):
            conn.close()
            closed.append(conn)

        async def connect(selector):
            return _SqliteConn()

        registry = empty_pool_registry()
        _, registry = await get_pool(registry, {"db_id": "scratch", "db_lifecycle": "on_demand"}, connect, 0)
        _, registry = await get_pool(registry, {"db_id": "main"}, connect, 0)
        # At t = 20ms with a 10ms threshold the on_demand pool is idle; the persistent one is never reaped.
        registry = await reap_idle(registry, 20 * ms, 10, close)
        if len(closed) != 1:
            bad.append(f"reap_idle should close exactly the idle on_demand pool: {closed}")
        if "main:" not in registry or "scratch:" in registry:
            bad.append(f"reap_idle should evict the on_demand pool and keep the persistent one: {list(registry)}")

        # A recently-used on_demand pool is not reaped.
        fresh = empty_pool_registry()
        _, fresh = await get_pool(fresh, {"db_id": "scratch", "db_lifecycle": "on_demand"}, connect, 100 * ms)
        fresh = await reap_idle(fresh, 105 * ms, 10, close)
        if "scratch:" not in fresh:
            bad.append("a recently-used on_demand pool should not be reaped")
        return bad

    return asyncio.run(_run())


def _probe_ephemeral():
    """Ephemeral lifecycle (§8.2): recreate_ephemeral connects, applies the target schema, and caches
    a pool for each ephemeral database in configuration order — exercised against real in-memory
    SQLite, then the recreated schema is used to insert and read a row, proving the table is real."""
    from honest_persist import execute, insert, recreate_ephemeral, select

    async def _run():
        bad = []
        connected = []

        async def connect(selector):
            connected.append(selector["database"])
            return _SqliteConn()

        config = [
            {"db_id": "keep", "db_lifecycle": "persistent", "schema": {"a": {"columns": {"id": {"type": "integer"}}}}},
            {"db_id": "scratch", "db_lifecycle": "ephemeral", "schema": {"t": {"columns": {"id": {"type": "integer"}, "name": {"type": "text"}}}}},
            {"db_id": "session", "db_lifecycle": "ephemeral", "schema": {"s": {"columns": {"k": {"type": "integer"}}}}},
        ]
        registry = await recreate_ephemeral(config, connect, "sqlite", 0)
        if connected != ["scratch", "session"]:
            bad.append(f"only ephemeral databases are recreated, in configuration order: {connected}")
        if "scratch:" not in registry or "keep:" in registry:
            bad.append(f"the registry should hold the ephemeral pools, not the persistent one: {list(registry)}")

        # The recreated schema is real: insert and read a row through the cached connection.
        conn = registry["scratch:"]["conn"]
        await execute(insert("t", {"id": 1, "name": "ada"}), conn)
        rows = await execute(select("t", ["name"]), conn)
        if rows != [{"name": "ada"}]:
            bad.append(f"the recreated ephemeral schema should accept and return a row: {rows}")
        return bad

    return asyncio.run(_run())


def _probe_pool_events():
    """Pool events (§8.8): get_pool emits hf.persist.pool 'created' on first contact (not on reuse),
    reap_idle emits 'closed' on eviction, both through the injected emit and keyed by the pool
    aggregate; emit_pool_event swallows a failing emit, and no emit means no event."""
    from honest_persist import emit_pool_event, empty_pool_registry, get_pool, reap_idle

    ms = 1_000_000

    async def _run():
        bad = []
        events = []

        async def emit(event_type, aggregate_type, aggregate_id, payload):
            events.append((event_type, aggregate_type, aggregate_id, payload))

        async def connect(selector):
            return _SqliteConn()

        async def close(conn):
            conn.close()

        registry = empty_pool_registry()
        _, registry = await get_pool(registry, {"db_id": "main", "db_lifecycle": "on_demand"}, connect, 0, emit)
        if len(events) != 1 or events[0][:3] != ("hf.persist.pool", "pool", "main") or events[0][3]["event"] != "created":
            bad.append(f"first contact should emit a pool created event: {events}")

        # Reuse does not re-emit created.
        _, registry = await get_pool(registry, {"db_id": "main", "db_lifecycle": "on_demand"}, connect, 1, emit)
        if len(events) != 1:
            bad.append("reusing a cached pool should not emit a created event")

        # Reaping emits closed.
        registry = await reap_idle(registry, 20 * ms, 10, close, emit)
        if len(events) != 2 or events[1][2] != "main" or events[1][3]["event"] != "closed":
            bad.append(f"reaping a pool should emit a closed event: {events}")

        # A failing emit is swallowed; no emit is a no-op.
        async def emit_down(event_type, aggregate_type, aggregate_id, payload):
            raise ValueError("emit is down")

        pool_down_err = io.StringIO()
        with redirect_stderr(pool_down_err):
            await emit_pool_event(emit_down, "x", "error", 1, 0, 1, None, "pool_exhausted", "saturated")
        if "pool event emit failed" not in pool_down_err.getvalue():
            bad.append(f"a failing pool-event emit should be swallowed and logged: {pool_down_err.getvalue()!r}")
        none_err = io.StringIO()
        with redirect_stderr(none_err):
            await emit_pool_event(None, "x", "created", 1, 1, 0, None, None, None)
        if none_err.getvalue():
            bad.append(f"a no-emit pool event should not touch emit (no stderr): {none_err.getvalue()!r}")
        return bad

    return asyncio.run(_run())


def _probe_write_queue():
    """The optimistic write queue (§8.6): merge_pending folds the pending writes for a table into a
    read by primary key (a pending insert appears, an update overrides, a delete vanishes); drain
    persists the queue to the backend through the injected execute — exercised against real SQLite
    for insert, update, and delete."""
    from honest_persist import drain_queue, empty_write_queue, enqueue_write, execute, merge_pending, raw, select
    from honest_persist.queue import is_stalled

    async def _run():
        bad = []
        # is_stalled fires once the failure has persisted for the six-hour limit. The boundary is pinned
        # with the literal STALL_NS (6 * 3600 * 1e9 = 21_600_000_000_000) so a shift of any factor or the
        # >= comparator is caught: exactly at the limit stalls, one nanosecond short does not.
        if is_stalled(0, 21_600_000_000_000) is not True:
            bad.append("is_stalled should fire exactly at the six-hour limit")
        if is_stalled(0, 21_599_999_999_999) is not False:
            bad.append("is_stalled should not fire one nanosecond before the limit")

        # Read transparency: pending writes fold into a SELECT by primary key; other tables ignored.
        rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        pending = empty_write_queue()
        pending = enqueue_write(pending, "insert", "t", {"id": 3, "name": "c"})
        pending = enqueue_write(pending, "update", "t", {"id": 1, "name": "A"})
        pending = enqueue_write(pending, "delete", "t", {"id": 2, "name": "b"})
        pending = enqueue_write(pending, "insert", "other", {"id": 9, "name": "x"})
        merged = merge_pending(rows, pending, "t", "id")
        if merged != [{"id": 1, "name": "A"}, {"id": 3, "name": "c"}]:
            bad.append(f"merge_pending should fold pending writes for the table by primary key: {merged}")

        # Drain against real SQLite: two inserts, then an update and a delete.
        conn = _SqliteConn()
        await execute(raw("CREATE TABLE t (id integer primary key, name text)"), conn)
        inserts = enqueue_write(enqueue_write(empty_write_queue(), "insert", "t", {"id": 1, "name": "a"}), "insert", "t", {"id": 2, "name": "b"})
        drained = await drain_queue(inserts, conn, execute, "id")
        if drained != []:
            bad.append("drain_queue should return the empty queue")
        if await execute(select("t", ["id", "name"]), conn) != [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]:
            bad.append("drained inserts should reach the backend")
        change = enqueue_write(enqueue_write(empty_write_queue(), "update", "t", {"id": 1, "name": "z"}), "delete", "t", {"id": 2, "name": "b"})
        await drain_queue(change, conn, execute, "id")
        if await execute(select("t", ["id", "name"]), conn) != [{"id": 1, "name": "z"}]:
            bad.append("a drained update and delete should reach the backend")
        return bad

    return asyncio.run(_run())


def _probe_supervisor():
    """Durability + the supervised drain (§8.6): the queue survives a restart through its JSONL file,
    and supervise_drain drains with retry, raising and emitting queue_stalled only once it has been
    failing past the six-hour limit — driven against a real temp file and real SQLite."""
    import tempfile

    from honest_persist import (
        backoff_delay,
        empty_write_queue,
        enqueue_write,
        execute,
        load_queue,
        raw,
        save_queue,
        supervise_drain,
    )

    hour = 3600 * 1_000_000_000

    async def _run():
        bad = []
        if backoff_delay(0, 100) != 100 or backoff_delay(3, 100) != 800:
            bad.append("backoff_delay should double the base per attempt")

        # Durability: a missing file is empty; save then load round-trips the queue through JSONL.
        writes = enqueue_write(enqueue_write(empty_write_queue(), "insert", "t", {"id": 1, "name": "a"}), "delete", "t", {"id": 2, "name": "b"})
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/queue.jsonl"
            if load_queue(path) != []:
                bad.append("loading a missing queue file should give an empty queue")
            save_queue(writes, path)
            if load_queue(path) != writes:
                bad.append("the queue should survive a save/load round-trip through JSONL")

        # A successful supervised drain against SQLite clears the queue and resets the failure clock.
        conn = _SqliteConn()
        await execute(raw("CREATE TABLE t (id integer primary key, name text)"), conn)
        insert_only = enqueue_write(empty_write_queue(), "insert", "t", {"id": 1, "name": "a"})
        drained, failure, ok_first = await supervise_drain(insert_only, conn, execute, "id", 0, None, None)
        if not ok_first or drained != [] or failure is not None:
            bad.append(f"a successful drain should clear the queue and reset the clock: {drained}, {failure}, {ok_first}")

        async def boom(query, connection):
            raise RuntimeError("backend down")

        # A failing drain keeps the queue and starts the failure clock, not yet stalled.
        kept, started, ok_fail = await supervise_drain(insert_only, conn, boom, "id", 100, None, None)
        if ok_fail or kept != insert_only or started != 100:
            bad.append(f"a failed drain should keep the queue and start the clock: {kept}, {started}, {ok_fail}")

        # Past six hours it emits queue_stalled and raises; a no-op emit and a failing emit are both fine.
        events = []

        async def emit(event_type, aggregate_type, aggregate_id, payload):
            events.append((event_type, aggregate_type, aggregate_id, payload))

        async def emit_down(event_type, aggregate_type, aggregate_id, payload):
            raise ValueError("emit is down")

        down_err = io.StringIO()
        none_err = io.StringIO()
        for sink, label, capture in ((emit, "emit", io.StringIO()), (None, "no emit", none_err), (emit_down, "failing emit", down_err)):
            raised = False
            try:
                with redirect_stderr(capture):
                    await supervise_drain(insert_only, conn, boom, "id", 7 * hour, 0, sink)
            except RuntimeError:
                raised = True
            if not raised:
                bad.append(f"a stalled queue should still raise the fault with {label}")
        if none_err.getvalue():
            bad.append(f"a no-emit stalled queue should not touch emit (no stderr): {none_err.getvalue()!r}")
        if not events or events[0][:3] != ("hf.persist.queue_stalled", "persist", "write_queue"):
            bad.append(f"a stalled queue should emit hf.persist.queue_stalled for the write_queue: {events}")
        elif events[0][3] != {"queue_depth": len(insert_only), "stalled_for_ns": 7 * hour, "fault_code": "queue_stalled"}:
            bad.append(f"the queue_stalled payload should carry the depth, stall time, and fault code: {events[0][3]}")
        if "queue_stalled emit failed" not in down_err.getvalue():
            bad.append(f"a swallowed queue_stalled emit failure should log to stderr: {down_err.getvalue()!r}")
        return bad

    return asyncio.run(_run())


def _probe_drain_loop():
    """The supervisor's drain loop and durable enqueue (§8.6): enqueue_durable persists the queue on
    every write so it survives a restart; run_drain_loop retries a failing backend with exponential
    backoff until it drains, and raises once it has stalled past the limit — driven with an injected
    clock and sleep against real SQLite and a real temp file."""
    import tempfile

    from honest_persist import (
        empty_write_queue,
        enqueue_durable,
        enqueue_write,
        execute,
        load_queue,
        raw,
        run_drain_loop,
        select,
    )

    hour = 3600 * 1_000_000_000

    async def _run():
        bad = []

        # Durable enqueue: every write is persisted, so the queue survives a restart.
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/queue.jsonl"
            queue = enqueue_durable(empty_write_queue(), "insert", "t", {"id": 1, "name": "a"}, path)
            if queue != [{"op": "insert", "table": "t", "row": {"id": 1, "name": "a"}}]:
                bad.append(f"enqueue_durable should return the new queue: {queue}")
            if load_queue(path) != queue:
                bad.append("enqueue_durable should persist the queue so it survives a restart")

        conn = _SqliteConn()
        await execute(raw("CREATE TABLE t (id integer primary key, name text)"), conn)
        queue = enqueue_write(empty_write_queue(), "insert", "t", {"id": 1, "name": "a"})

        # run_drain_loop retries a failing-then-succeeding backend, sleeping the exponential backoff.
        attempts = {"n": 0}

        async def flaky(query, connection):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("transient")
            await execute(query, connection)

        slept = []

        async def sleep(milliseconds):
            slept.append(milliseconds)

        ticks = {"t": 0}

        def now():
            ticks["t"] += 1
            return ticks["t"]

        drained = await run_drain_loop(queue, conn, flaky, "id", 10, now, sleep, None)
        if drained != [] or attempts["n"] != 3 or slept != [20, 40]:
            bad.append(f"run_drain_loop should retry with exponential backoff until it drains: {attempts}, {slept}")
        if await execute(select("t", ["id", "name"]), conn) != [{"id": 1, "name": "a"}]:
            bad.append("the write should reach the backend once the loop drains")

        # A perpetually failing backend, with the clock past the limit, stalls and raises.
        async def always_fail(query, connection):
            raise RuntimeError("backend down")

        jumps = {"t": 0}

        def jump_now():
            jumps["t"] += 7 * hour
            return jumps["t"]

        raised = False
        try:
            await run_drain_loop(queue, conn, always_fail, "id", 10, jump_now, sleep, None)
        except RuntimeError:
            raised = True
        if not raised:
            bad.append("a perpetually failing drain loop should eventually stall and raise")
        return bad

    return asyncio.run(_run())


def _probe_connection_pool():
    """The multi-connection pool (§8.1, 8.3, 8.8): new_pool / acquire / release manage N connections
    as a value — acquire faults pool_exhausted when every one is in use; open_pool establishes each
    connection resiliently through connect_with_retry and emits created, closing the ones already
    opened if a later one cannot be established; lease emits exhausted on a full pool, close emits
    closed — open and close driven against real SQLite connections."""
    from honest_persist import (
        acquire_connection,
        close_pool,
        lease_connection,
        new_pool,
        open_pool,
        release_connection,
    )

    async def _run():
        bad = []

        # Pure mechanics: acquire hands out idle connections, faults when full, release returns one.
        pool = new_pool(["c1", "c2"])
        if pool != {"size": 2, "idle": ["c1", "c2"], "active": 0}:
            bad.append(f"new_pool should hold the connections idle: {pool}")
        first, pool = acquire_connection(pool)
        second, pool = acquire_connection(pool)
        if first["ok"] != "c1" or second["ok"] != "c2" or pool["active"] != 2:
            bad.append(f"acquire should hand out idle connections and count them active: {first}, {second}, {pool}")
        miss, pool = acquire_connection(pool)
        if miss.get("err", {}).get("code") != "pool_exhausted":
            bad.append(f"acquire on a full pool should fault pool_exhausted: {miss}")
        pool = release_connection(pool, "c1")
        if pool["active"] != 1 or "c1" not in pool["idle"]:
            bad.append(f"release should return the connection to idle: {pool}")

        # open_pool against real SQLite: each connection is established resiliently through
        # connect_with_retry, so a transient failure retries, and a created event fires once the
        # whole pool is open.
        created = []

        async def emit_created(event_type, aggregate_type, aggregate_id, payload):
            created.append(payload)

        def classify(exc):
            return "unresolvable_dsn"

        async def sleep(delay_ms):
            return None

        attempts = {"n": 0}

        async def flaky_connect(selector):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("connection refused")
            return _SqliteConn()

        async def close_unused(conn):
            conn.close()

        opened = await open_pool("main", flaky_connect, classify, close_unused, 2, 3, 10, sleep, emit_created)
        if "ok" not in opened or opened["ok"]["size"] != 2 or [p["event"] for p in created] != ["retry", "created"]:
            bad.append(f"open_pool should establish each connection resiliently and emit created: {opened}, {[p['event'] for p in created]}")
        elif (created[-1]["pool_size"], created[-1]["active"], created[-1]["waiting"]) != (2, 0, 0):
            bad.append(f"the created pool event should report the pool size and no active/waiting: {created[-1]}")

        # A connection that cannot be established closes the ones already opened — none leak — and
        # returns the establishment fault.
        made = []

        async def first_then_down(selector):
            if not made:
                conn = _SqliteConn()
                made.append(conn)
                return conn
            raise RuntimeError("connection refused")

        cleaned = []

        async def close_partial(conn):
            conn.close()
            cleaned.append(conn)

        async def emit_partial(event_type, aggregate_type, aggregate_id, payload):
            return None

        partial = await open_pool("main", first_then_down, classify, close_partial, 2, 1, 1, sleep, emit_partial)
        if partial.get("err", {}).get("code") != "unresolvable_dsn" or cleaned != made:
            bad.append(f"open_pool should close the connections it opened when a later one fails: {partial}, {cleaned}, {made}")

        # lease emits exhausted on a full pool, and stays quiet when a connection is free.
        exhausted = []

        async def emit_exhausted(event_type, aggregate_type, aggregate_id, payload):
            exhausted.append(payload["event"])

        result, _ = await lease_connection(new_pool([]), "main", emit_exhausted)
        if result.get("err", {}).get("code") != "pool_exhausted" or exhausted != ["exhausted"]:
            bad.append(f"lease on a full pool should fault and emit exhausted: {result}, {exhausted}")
        quiet = []

        async def emit_quiet(event_type, aggregate_type, aggregate_id, payload):
            quiet.append(payload["event"])

        leased, _ = await lease_connection(new_pool(["c1"]), "main", emit_quiet)
        if "ok" not in leased or quiet != []:
            bad.append(f"lease with a free connection should not emit exhausted: {leased}, {quiet}")

        # close_pool closes the idle connections and emits closed.
        closed_conns = []

        async def close(conn):
            conn.close()
            closed_conns.append(conn)

        closed_events = []

        async def emit_closed(event_type, aggregate_type, aggregate_id, payload):
            closed_events.append(payload["event"])

        await close_pool(opened["ok"], "main", close, emit_closed)
        if len(closed_conns) != 2 or closed_events != ["closed"]:
            bad.append(f"close_pool should close the idle connections and emit closed: {closed_conns}, {closed_events}")
        return bad

    return asyncio.run(_run())


def _probe_connect_retry():
    """Resilient connection establishment (section 8.8, 8.3): connect_with_retry retries a transient
    failure — emitting a retry event and sleeping the backoff — then connects against a real SQLite
    database; exhausts its attempts on a persistently unresolvable DSN, emitting error and returning
    err(unresolvable_dsn); and fails fast on a rejected credential without retrying at all.
    should_retry is the pure decision underneath."""
    from honest_persist import connect_with_retry, should_retry

    async def _run():
        bad = []

        # The pure decision: retry while attempts remain and the fault is transient.
        if not should_retry(0, 3, "unresolvable_dsn"):
            bad.append("should_retry should retry a transient fault while attempts remain")
        if should_retry(3, 3, "unresolvable_dsn"):
            bad.append("should_retry should stop once the attempts are exhausted")
        if should_retry(0, 3, "credential_rejected"):
            bad.append("should_retry should never retry a credential_rejected fault")

        def classify(exc):
            return "credential_rejected" if "denied" in str(exc) else "unresolvable_dsn"

        # A transient failure retries once, sleeps the backoff, then connects for real.
        attempts = {"n": 0}

        async def flaky(selector):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise RuntimeError("connection refused")
            return _SqliteConn()

        retries_seen = []

        async def emit(event_type, aggregate_type, aggregate_id, payload):
            retries_seen.append(payload)

        slept = []

        async def sleep(delay_ms):
            slept.append(delay_ms)

        opened = await connect_with_retry({"database": "main"}, flaky, classify, 3, 10, sleep, emit)
        if "ok" not in opened or [p["event"] for p in retries_seen] != ["retry"] or slept != [20]:
            bad.append(f"a transient failure should retry once, sleep the backoff, then connect: {opened}, {retries_seen}, {slept}")
        elif (retries_seen[0]["pool_size"], retries_seen[0]["active"], retries_seen[0]["waiting"]) != (0, 0, 0):
            bad.append(f"a retry pool event should report no pool counters yet (0/0/0): {retries_seen[0]}")
        else:
            conn = opened["ok"]
            await conn.execute("CREATE TABLE t (x INTEGER)")
            await conn.execute("INSERT INTO t (x) VALUES (1)")
            got = await conn.execute("SELECT x FROM t")
            if got["rows"][0]["x"] != 1:
                bad.append(f"connect_with_retry should return a usable connection: {got}")

        # A persistently unresolvable DSN exhausts its retries and emits error.
        async def down(selector):
            raise RuntimeError("connection refused")

        down_events = []

        async def emit_down(event_type, aggregate_type, aggregate_id, payload):
            down_events.append(payload)

        async def sleep_noop(delay_ms):
            return None

        failed = await connect_with_retry({"database": "main"}, down, classify, 2, 10, sleep_noop, emit_down)
        if failed.get("err", {}).get("code") != "unresolvable_dsn" or [p["event"] for p in down_events] != ["retry", "retry", "error"]:
            bad.append(f"an unresolvable DSN should exhaust its retries and emit error: {failed}, {[p['event'] for p in down_events]}")
        elif (down_events[-1]["pool_size"], down_events[-1]["active"], down_events[-1]["waiting"]) != (0, 0, 0):
            bad.append(f"an error pool event should report no pool counters (0/0/0): {down_events[-1]}")

        # A rejected credential fails fast: no retry, no sleep.
        async def denied(selector):
            raise RuntimeError("access denied")

        denied_events = []

        async def emit_denied(event_type, aggregate_type, aggregate_id, payload):
            denied_events.append(payload["event"])

        denied_slept = []

        async def sleep_denied(delay_ms):
            denied_slept.append(delay_ms)

        rejected = await connect_with_retry({"database": "main"}, denied, classify, 3, 10, sleep_denied, emit_denied)
        if rejected.get("err", {}).get("code") != "credential_rejected" or denied_events != ["error"] or denied_slept != []:
            bad.append(f"a rejected credential should fail fast without retrying: {rejected}, {denied_events}, {denied_slept}")
        return bad

    return asyncio.run(_run())


def _probe_migrate():
    """The migration workflow (section 9): inspect reads the live SQLite schema back, and migrate
    composes inspect + diff + apply against a real database — creating a table, then adding a column
    on a second pass — refusing without applying when the diff is ambiguous, surfacing a diff fault
    for an invalid target, and faulting on an unsupported dialect. Driven end-to-end on real SQLite."""
    from honest_persist import inspect, migrate

    async def _run():
        bad = []

        # inspect reads tables and columns back with type, nullability, primary key, and default.
        rich = _SqliteConn()
        await rich.execute(
            "CREATE TABLE rich (id integer PRIMARY KEY, label text NOT NULL, score integer DEFAULT 5, note text)"
        )
        read = await inspect(rich, "sqlite")
        if set(read["ok"]) != {"rich"}:
            bad.append(f"inspect should read exactly the user tables: {read}")
        else:
            cols = read["ok"]["rich"]["columns"]
            if cols["id"] != {"type": "integer", "nullable": True, "primary_key": True}:
                bad.append(f"inspect should read the primary key column: {cols.get('id')}")
            if cols["label"] != {"type": "text", "nullable": False}:
                bad.append(f"inspect should read a NOT NULL column: {cols.get('label')}")
            if cols["score"] != {"type": "integer", "nullable": True, "default": "5"}:
                bad.append(f"inspect should read a column default: {cols.get('score')}")
            if cols["note"] != {"type": "text", "nullable": True}:
                bad.append(f"inspect should read a plain nullable column: {cols.get('note')}")

        # migrate creates the table on an empty database, then adds a column on the next pass.
        conn = _SqliteConn()
        v1 = {"notes": {"columns": {"body": {"type": "text", "nullable": True}, "ts": {"type": "integer", "nullable": True}}}}
        first = await migrate(v1, conn, "sqlite")
        if "ok" not in first or not first["ok"]["success"]:
            bad.append(f"migrate should create the table on an empty database: {first}")
        v2 = {"notes": {"columns": {"body": {"type": "text", "nullable": True}, "ts": {"type": "integer", "nullable": True}, "tag": {"type": "text", "nullable": True}}}}
        second = await migrate(v2, conn, "sqlite")
        after = await inspect(conn, "sqlite")
        if "ok" not in second or "tag" not in after["ok"]["notes"]["columns"]:
            bad.append(f"migrate should add the new column on the second pass: {second}, {after}")

        # An ambiguous diff (a likely rename) is refused — the database is left untouched.
        amb = _SqliteConn()
        await amb.execute("CREATE TABLE acct (emial text)")
        renamed = {"acct": {"columns": {"email": {"type": "text", "nullable": True}}}}
        refused = await migrate(renamed, amb, "sqlite")
        still = await inspect(amb, "sqlite")
        err_amb = refused.get("err", {})
        if err_amb.get("code") != "migration_ambiguous" or err_amb.get("message") != "Diff is ambiguous; a human must resolve the renames before applying" or err_amb.get("category") != "server" or "ambiguities" not in (err_amb.get("detail") or {}):
            bad.append(f"the ambiguous-diff fault should be fully named with its ambiguities: {refused}")
        if "emial" not in still["ok"]["acct"]["columns"]:
            bad.append(f"migrate should refuse an ambiguous diff without applying: {still}")

        # An invalid target schema fails at the diff, before any apply.
        broken = _SqliteConn()
        invalid = {"orders": {"columns": {"id": {"type": "integer", "nullable": True}}, "primary_key": ["missing"]}}
        rejected = await migrate(invalid, broken, "sqlite")
        if rejected.get("err", {}).get("code") != "schema_invalid":
            bad.append(f"migrate should surface a diff fault for an invalid target: {rejected}")

        # An unsupported dialect has no inspector.
        nodb = _SqliteConn()
        unknown = await migrate({}, nodb, "oracle")
        if unknown.get("err") != {"code": "unsupported_dialect", "message": "no schema inspector for dialect 'oracle'", "category": "server", "detail": {}}:
            bad.append(f"the unsupported-dialect fault should be fully named: {unknown}")

        # §6.2: a CHECK that can be neither natively enforced nor compiled is refused at construction,
        # before any DDL touches the database, not silently dropped to surface at the first write.
        badcheck = _SqliteConn()
        target = {"t": {"columns": {"id": {"type": "integer", "nullable": True}, "x": {"type": "integer", "nullable": True, "check": "x @@ 1"}}}}
        construction = await migrate(target, badcheck, "turso")
        left = await inspect(badcheck, "turso")
        if construction.get("err", {}).get("code") != "uncompilable_check" or "t" in left["ok"]:
            bad.append(f"migrate should refuse an uncompilable CHECK at construction without applying: {construction}, {left}")
        return bad

    return asyncio.run(_run())


def _probe_abstractions():
    """The abstraction layer (section 6): expand_schema rewrites a range column into its lower/upper
    bound columns and a lower<=upper CHECK and leaves a plain schema unchanged; the range predicates
    build parameterized WHERE conditions over the bounds; and a migrated range schema enforces the
    bound invariant on real SQLite (the CHECK rejects a row whose lower exceeds its upper)."""
    from honest_persist import expand_schema, migrate, range_adjacent, range_contains, range_overlaps

    async def _run():
        bad = []

        # expand_schema rewrites a range column to bound columns + a CHECK; plain columns pass through.
        schema = {"events": {"columns": {
            "id": {"type": "integer", "nullable": False},
            "span": {"type": "range", "bound_type": "integer", "nullable": False},
        }}}
        expanded = expand_schema(schema)
        cols = expanded["events"]["columns"]
        if set(cols) != {"id", "span_lower", "span_upper"}:
            bad.append(f"expand_schema should replace the range with bound columns: {cols}")
        elif cols["span_lower"] != {"type": "integer", "nullable": False} or cols["span_upper"] != {"type": "integer", "nullable": False}:
            bad.append(f"expand_schema should give each bound the bound_type and nullability: {cols}")
        check = expanded["events"].get("constraints", {}).get("span_range")
        if check != {"type": "check", "expression": "span_lower <= span_upper"}:
            bad.append(f"expand_schema should add the lower<=upper CHECK: {check}")
        plain = {"t": {"columns": {"a": {"type": "text"}}}}
        if expand_schema(plain) != plain:
            bad.append("expand_schema should leave a plain schema unchanged in shape")
        # A range column without a declared nullability gives bounds without a nullable key.
        loose = expand_schema({"r": {"columns": {"s": {"type": "range", "bound_type": "text"}}}})
        if loose["r"]["columns"]["s_lower"] != {"type": "text"}:
            bad.append(f"a range without nullability should give a plain bound column: {loose}")

        # the predicates build parameterized conditions over the bound columns.
        if range_overlaps("span", 3, 9) != {"sql": "span_lower <= :span_ub AND span_upper >= :span_lb", "params": {"span_ub": 9, "span_lb": 3}}:
            bad.append(f"range_overlaps wrong: {range_overlaps('span', 3, 9)}")
        if range_contains("span", 5) != {"sql": "span_lower <= :span_pt AND span_upper >= :span_pt", "params": {"span_pt": 5}}:
            bad.append(f"range_contains wrong: {range_contains('span', 5)}")
        if range_adjacent("span", 3, 9) != {"sql": "span_upper = :span_adj_l OR span_lower = :span_adj_u", "params": {"span_adj_l": 3, "span_adj_u": 9}}:
            bad.append(f"range_adjacent wrong: {range_adjacent('span', 3, 9)}")

        # _render_create_table renders a CHECK constraint inline; other table-constraint types are
        # not inline-rendered on create.
        from honest_persist import to_sql

        mixed = {"op": "create_table", "table": "t", "details": {
            "columns": {"a": {"type": "text"}},
            "constraints": {"chk": {"type": "check", "expression": "a <> ''"}, "uq": {"type": "unique", "columns": ["a"]}},
        }}
        rendered_sql = to_sql(mixed, "sqlite")
        if "CONSTRAINT chk CHECK (a <> '')" not in rendered_sql:
            bad.append(f"_render_create_table should render a CHECK constraint inline: {rendered_sql}")
        if "CONSTRAINT uq" in rendered_sql:
            bad.append(f"only CHECK table constraints are rendered inline on create: {rendered_sql}")

        # migrate a range schema to real SQLite: the CHECK enforces lower <= upper.
        conn = _SqliteConn()
        applied = await migrate(schema, conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"migrate should apply the expanded range schema: {applied}")
        else:
            await conn.execute("INSERT INTO events (id, span_lower, span_upper) VALUES (1, 3, 9)")
            good = await conn.execute("SELECT span_lower, span_upper FROM events")
            if good["rows"][0]["span_lower"] != 3:
                bad.append(f"a valid range row should insert: {good}")
            rejected = False
            try:
                await conn.execute("INSERT INTO events (id, span_lower, span_upper) VALUES (2, 9, 3)")
            except Exception:
                rejected = True
            if not rejected:
                bad.append("the CHECK should reject a row whose lower bound exceeds its upper")
        return bad

    return asyncio.run(_run())


def _probe_arrays_maps():
    """Arrays and maps (section 6.4): expand_schema removes an array or map column and generates its
    junction table — owner_id typed from the base primary key — and the element operations build
    queries over the junction; a migrated array schema round-trips on real SQLite."""
    from honest_persist import (
        array_append,
        array_reindex,
        array_remove,
        array_set,
        expand_schema,
        map_put,
        map_remove,
        migrate,
    )

    async def _run():
        bad = []

        # An array column becomes a junction table; the base column is removed. owner_id takes the
        # base table's primary-key type (here a text id).
        schema = {"posts": {"columns": {
            "id": {"type": "text", "primary_key": True},
            "tags": {"type": "array", "element_type": "text"},
        }}}
        expanded = expand_schema(schema)
        if set(expanded["posts"]["columns"]) != {"id"}:
            bad.append(f"expand_schema should remove the array column from the base table: {expanded['posts']}")
        junction = expanded.get("_hp_array_posts_tags", {}).get("columns", {})
        if junction.get("owner_id") != {"type": "text", "nullable": False} or junction.get("ordinal") != {"type": "integer", "nullable": False} or junction.get("value") != {"type": "text", "nullable": False}:
            bad.append(f"expand_schema should generate the array junction table: {junction}")

        # A map column becomes a junction with key/value; owner_id from a table-level primary key.
        mapped = expand_schema({"u": {"columns": {"uid": {"type": "integer"}, "prefs": {"type": "map", "key_type": "text", "value_type": "text"}}, "primary_key": ["uid"]}})
        mj = mapped.get("_hp_map_u_prefs", {}).get("columns", {})
        if mj.get("owner_id") != {"type": "integer", "nullable": False} or mj.get("key") != {"type": "text", "nullable": False}:
            bad.append(f"expand_schema should generate the map junction from the table primary-key owner type: {mj}")

        # No declared primary key falls back to an integer owner_id.
        noid = expand_schema({"t": {"columns": {"xs": {"type": "array", "element_type": "integer"}}}})
        if noid["_hp_array_t_xs"]["columns"]["owner_id"] != {"type": "integer", "nullable": False}:
            bad.append(f"a junction owner should default to integer with no primary key: {noid}")
        # A table-level primary key naming no real column also falls back to integer.
        ghost = expand_schema({"g": {"columns": {"xs": {"type": "array", "element_type": "text"}}, "primary_key": ["ghost"]}})
        if ghost["_hp_array_g_xs"]["columns"]["owner_id"] != {"type": "integer", "nullable": False}:
            bad.append(f"a junction owner should default to integer when the primary key names no column: {ghost}")

        # The element operations build queries over the junction table.
        if array_append("posts", "tags", "p1", 0, "x") != {"sql": "INSERT INTO _hp_array_posts_tags (owner_id, ordinal, value) VALUES (:owner_id, :ordinal, :value)", "params": {"owner_id": "p1", "ordinal": 0, "value": "x"}}:
            bad.append(f"array_append wrong: {array_append('posts', 'tags', 'p1', 0, 'x')}")
        if "SET value = :set_value" not in array_set("posts", "tags", "p1", 0, "y")["sql"]:
            bad.append(f"array_set wrong: {array_set('posts', 'tags', 'p1', 0, 'y')}")
        if array_remove("posts", "tags", "p1", 0)["sql"] != "DELETE FROM _hp_array_posts_tags WHERE owner_id = :owner_id AND ordinal = :ordinal":
            bad.append(f"array_remove wrong: {array_remove('posts', 'tags', 'p1', 0)}")
        if array_reindex("posts", "tags", "p1", 0) != {"sql": "UPDATE _hp_array_posts_tags SET ordinal = ordinal - 1 WHERE owner_id = :owner_id AND ordinal > :removed", "params": {"owner_id": "p1", "removed": 0}}:
            bad.append(f"array_reindex wrong: {array_reindex('posts', 'tags', 'p1', 0)}")
        if map_put("posts", "meta", "p1", "k", "v")["sql"] != "INSERT INTO _hp_map_posts_meta (owner_id, key, value) VALUES (:owner_id, :key, :value)":
            bad.append(f"map_put wrong: {map_put('posts', 'meta', 'p1', 'k', 'v')}")
        if map_remove("posts", "meta", "p1", "k")["sql"] != "DELETE FROM _hp_map_posts_meta WHERE owner_id = :owner_id AND key = :key":
            bad.append(f"map_remove wrong: {map_remove('posts', 'meta', 'p1', 'k')}")

        # migrate an array schema to real SQLite: base table + junction created, an element round-trips.
        conn = _SqliteConn()
        applied = await migrate(schema, conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"migrate should create the base and junction tables: {applied}")
        else:
            await conn.execute("INSERT INTO posts (id) VALUES ('p1')")
            op = array_append("posts", "tags", "p1", 0, "urgent")
            await conn.execute(op["sql"], op["params"])
            got = await conn.execute("SELECT value FROM _hp_array_posts_tags WHERE owner_id = 'p1'")
            if got["rows"][0]["value"] != "urgent":
                bad.append(f"an appended array element should round-trip: {got}")
        return bad

    return asyncio.run(_run())


def _probe_hierarchy():
    """Hierarchy (section 6.3): expand_schema rewrites a hierarchy column to a nullable parent plus a
    closure table; the maintenance builders insert nodes, read ancestors and descendants in one
    query, move a subtree, and delete a subtree — all proven on a real SQLite tree."""
    from honest_persist import (
        closure_ancestors,
        closure_delete,
        closure_descendants,
        closure_insert,
        closure_move,
        expand_schema,
        migrate,
    )

    async def _run():
        bad = []

        # expand_schema rewrites the hierarchy column to a nullable parent and a closure table.
        schema = {"nodes": {"columns": {
            "id": {"type": "text", "primary_key": True},
            "parent": {"type": "hierarchy"},
        }}}
        expanded = expand_schema(schema)
        if expanded["nodes"]["columns"]["parent"] != {"type": "text", "nullable": True}:
            bad.append(f"expand_schema should make the hierarchy column a nullable parent: {expanded['nodes']}")
        closure = expanded.get("_hp_closure_nodes", {}).get("columns", {})
        if closure.get("ancestor") != {"type": "text", "nullable": False} or closure.get("depth") != {"type": "integer", "nullable": False}:
            bad.append(f"expand_schema should generate the closure table: {closure}")

        # build a real tree on SQLite: A root, B under A, C under B, D root.
        conn = _SqliteConn()
        applied = await migrate(schema, conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"migrate should create the base and closure tables: {applied}")
            return bad

        async def add(node, parent):
            await conn.execute("INSERT INTO nodes (id, parent) VALUES (:id, :p)", {"id": node, "p": parent})
            op = closure_insert("nodes", node, parent)
            await conn.execute(op["sql"], op["params"])

        await add("A", None)
        await add("B", "A")
        await add("C", "B")
        await add("D", None)

        async def ids(op, field):
            rows = (await conn.execute(op["sql"], op["params"]))["rows"]
            return sorted(row[field] for row in rows)

        if await ids(closure_descendants("nodes", "A"), "descendant") != ["A", "B", "C"]:
            bad.append("closure_descendants(A) should be the subtree {A, B, C}")
        if await ids(closure_ancestors("nodes", "C"), "ancestor") != ["A", "B", "C"]:
            bad.append("closure_ancestors(C) should be the chain {A, B, C}")

        # move subtree B under D: C's ancestors become {B, C, D}, no longer including A.
        for step in closure_move("nodes", "B", "D"):
            await conn.execute(step["sql"], step["params"])
        if await ids(closure_ancestors("nodes", "C"), "ancestor") != ["B", "C", "D"]:
            bad.append("after moving B under D, closure_ancestors(C) should be {B, C, D}")
        if await ids(closure_descendants("nodes", "D"), "descendant") != ["B", "C", "D"]:
            bad.append("after the move, D's subtree should be {B, C, D}")

        # delete subtree D: its whole subtree leaves the closure.
        d = closure_delete("nodes", "D")
        await conn.execute(d["sql"], d["params"])
        if await ids(closure_descendants("nodes", "D"), "descendant") != []:
            bad.append("after closure_delete(D), D's subtree should be empty")
        return bad

    return asyncio.run(_run())


def _probe_enums():
    """Enums (section 6.1): expand_schema rewrites a literal_values column to a seeded lookup table
    and a foreign-key column; enum_seed_queries builds idempotent inserts; and a migrated enum
    schema, with foreign keys enforced, accepts a declared value and rejects an undeclared one on
    real SQLite, the re-seed being idempotent."""
    from honest_persist import enum_seed_queries, expand_schema, migrate

    async def _run():
        bad = []

        schema = {"orders": {"columns": {
            "id": {"type": "integer", "primary_key": True},
            "status": {"literal_values": ["pending", "confirmed", "shipped"], "default": "'pending'"},
        }}}
        expanded = expand_schema(schema)
        status = expanded["orders"]["columns"]["status"]
        if status != {"type": "text", "references": "_hp_enum_orders_status.value", "default": "'pending'"}:
            bad.append(f"expand_schema should make the enum a foreign-key column: {status}")
        lookup = expanded.get("_hp_enum_orders_status", {})
        if lookup.get("columns", {}).get("value") != {"type": "text", "primary_key": True} or lookup.get("seed") != [{"value": "pending"}, {"value": "confirmed"}, {"value": "shipped"}]:
            bad.append(f"expand_schema should generate the seeded lookup table: {lookup}")
        # An enum with a declared nullability and no default keeps the nullability, omits the default.
        nullable = expand_schema({"t": {"columns": {"k": {"literal_values": ["a", "b"], "nullable": True}}}})["t"]["columns"]["k"]
        if nullable != {"type": "text", "references": "_hp_enum_t_k.value", "nullable": True}:
            bad.append(f"an enum column should keep its nullability and omit an absent default: {nullable}")

        # enum_seed_queries builds idempotent inserts; the dialect sets the ignore form.
        if enum_seed_queries(expanded, "sqlite")[0] != {"sql": "INSERT OR IGNORE INTO _hp_enum_orders_status (value) VALUES (:value)", "params": {"value": "pending"}}:
            bad.append(f"enum_seed_queries (sqlite) wrong: {enum_seed_queries(expanded, 'sqlite')}")
        if enum_seed_queries(expanded, "postgresql")[0]["sql"] != "INSERT INTO _hp_enum_orders_status (value) VALUES (:value) ON CONFLICT DO NOTHING":
            bad.append(f"enum_seed_queries (postgresql) wrong: {enum_seed_queries(expanded, 'postgresql')}")

        # migrate to real SQLite with foreign keys enforced: declared values pass, others are rejected.
        conn = _SqliteConn()
        await conn.execute("PRAGMA foreign_keys = ON")
        applied = await migrate(schema, conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"migrate should create the enum lookup and base tables: {applied}")
        else:
            seeded = await conn.execute("SELECT value FROM _hp_enum_orders_status")
            if sorted(r["value"] for r in seeded["rows"]) != ["confirmed", "pending", "shipped"]:
                bad.append(f"the lookup table should be seeded with the enum values: {seeded}")
            await conn.execute("INSERT INTO orders (id, status) VALUES (1, 'confirmed')")
            kept = await conn.execute("SELECT status FROM orders WHERE id = 1")
            if kept["rows"][0]["status"] != "confirmed":
                bad.append(f"a declared enum value should insert: {kept}")
            rejected = False
            try:
                await conn.execute("INSERT INTO orders (id, status) VALUES (2, 'bogus')")
            except Exception:
                rejected = True
            if not rejected:
                bad.append("an undeclared enum value should be rejected by the foreign key")
            # Re-seeding is idempotent.
            for query in enum_seed_queries(expanded, "sqlite"):
                await conn.execute(query["sql"], query["params"])
            again = await conn.execute("SELECT count(*) AS n FROM _hp_enum_orders_status")
            if again["rows"][0]["n"] != 3:
                bad.append(f"re-seeding should be idempotent: {again}")

        # When apply fails, the workflow returns the failed result and runs no seed.
        broken = _SqliteConn()
        bad_schema = {"x": {"columns": {"a": {"type": "text"}}, "constraints": {"c": {"type": "check", "expression": "a a a"}}}}
        failed = await migrate(bad_schema, broken, "sqlite")
        if "ok" not in failed or failed["ok"]["success"]:
            bad.append(f"migrate should return the failed ApplyResult when apply fails, seeding nothing: {failed}")
        return bad

    return asyncio.run(_run())


def _probe_loader():
    """The Pydantic schema loader (section 2): @table-decorated BaseModel subclasses load to a Schema
    — field types mapped to abstract SQL types, Optional to nullability, Literal to enum values, Field
    metadata and defaults to column attributes, and a Meta inner class to a composite primary key,
    indexes, and constraints — and the loaded schema migrates to real SQLite."""
    from datetime import datetime
    from pathlib import Path
    from typing import Literal

    from pydantic import BaseModel, Field

    from honest_persist import migrate
    from honest_persist.loader import load_schema_from_models, table

    @table("items")
    class Item(BaseModel):
        id: int = Field(json_schema_extra={"primary": True})
        name: str = Field(json_schema_extra={"unique": True})
        owner: str = Field(json_schema_extra={"references": "users.value", "on_delete": "cascade"})
        status: Literal["a", "b"] = Field(json_schema_extra={"check": "status <> ''"})
        qty: int = Field(default=5)
        label: str = Field(default="x")
        active: bool = Field(default=True)
        ratio: float = Field(default=1.5)
        note: str | None = None
        flag: bool = Field(json_schema_extra={"nullable": True})
        when: datetime | None = None
        loc: Path | None = None
        tag: str = Field(json_schema_extra={"default": "'none'"})
        _internal: int = 0

    @table("memberships")
    class Membership(BaseModel):
        user_id: int = Field(json_schema_extra={"primary": True})
        group_id: int = Field(json_schema_extra={"primary": True})

        class Meta:
            primary_key = ["user_id", "group_id"]
            indexes = {"by_group": {"columns": ["group_id"]}}
            constraints = {"uniq": {"type": "unique", "columns": ["user_id", "group_id"]}}

    @table("widgets")
    class Widget(BaseModel):
        id: int = Field(json_schema_extra={"primary": True})
        label: str = Field(default="hi")

    bad = []
    cols = load_schema_from_models(Item)["items"]["columns"]
    expected = {
        "id": {"type": "integer", "nullable": False, "primary_key": True},
        "name": {"type": "text", "nullable": False, "unique": True},
        "owner": {"type": "text", "nullable": False, "references": "users.value", "on_delete": "cascade"},
        "status": {"type": "text", "nullable": False, "literal_values": ["a", "b"], "check": "status <> ''"},
        "qty": {"type": "integer", "nullable": False, "default": "5"},
        "label": {"type": "text", "nullable": False, "default": "'x'"},
        "active": {"type": "boolean", "nullable": False, "default": "TRUE"},
        "ratio": {"type": "real", "nullable": False, "default": "1.5"},
        "note": {"type": "text", "nullable": True},
        "flag": {"type": "boolean", "nullable": True},
        "when": {"type": "timestamptz", "nullable": True},
        "loc": {"type": "text", "nullable": True},
        "tag": {"type": "text", "nullable": False, "default": "'none'"},
    }
    if set(cols) != set(expected):
        bad.append(f"loader should map every public field and skip private ones: {sorted(cols)}")
    for field_name, exp in expected.items():
        if cols.get(field_name) != exp:
            bad.append(f"loader column {field_name}: got {cols.get(field_name)}, expected {exp}")

    # A model covering every _PY_TO_SQL type and the remaining metadata keys (db_type override,
    # primary_key alias, on_update, renamed_from), so each map entry and metadata branch is pinned.
    from datetime import date as _date, time as _time
    from decimal import Decimal as _Decimal
    from uuid import UUID as _UUID

    @table("typed")
    class Typed(BaseModel):
        raw: bytes
        uid: _UUID
        d: _date
        t: _time
        when: datetime
        amount: _Decimal
        blob: dict
        items: list
        custom: str = Field(json_schema_extra={"db_type": "citext"})
        pk: int = Field(json_schema_extra={"primary_key": True})
        upd: str = Field(json_schema_extra={"on_update": "cascade"})
        ren: str = Field(json_schema_extra={"renamed_from": "old"})

    typed_cols = load_schema_from_models(Typed)["typed"]["columns"]
    typed_expected = {
        "raw": {"type": "bytea", "nullable": False}, "uid": {"type": "uuid", "nullable": False},
        "d": {"type": "date", "nullable": False}, "t": {"type": "time", "nullable": False},
        "when": {"type": "timestamptz", "nullable": False}, "amount": {"type": "numeric", "nullable": False},
        "blob": {"type": "jsonb", "nullable": False}, "items": {"type": "jsonb", "nullable": False},
        "custom": {"type": "citext", "nullable": False}, "pk": {"type": "integer", "nullable": False, "primary_key": True},
        "upd": {"type": "text", "nullable": False, "on_update": "cascade"}, "ren": {"type": "text", "nullable": False, "renamed_from": "old"},
    }
    if typed_cols != typed_expected:
        bad.append(f"loader type map / metadata keys wrong: {typed_cols}")

    membership = load_schema_from_models(Membership)["memberships"]
    if membership.get("primary_key") != ["user_id", "group_id"]:
        bad.append(f"a Meta composite primary key should become the table primary key: {membership}")
    if "primary_key" in membership["columns"]["user_id"]:
        bad.append("a composite primary key should clear the per-column primary_key flags")
    if membership.get("indexes") != {"by_group": {"columns": ["group_id"]}} or membership.get("constraints") != {"uniq": {"type": "unique", "columns": ["user_id", "group_id"]}}:
        bad.append(f"a Meta should carry indexes and constraints: {membership}")

    async def _run():
        conn = _SqliteConn()
        applied = await migrate(load_schema_from_models(Widget), conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"a loaded schema should migrate: {applied}")
        else:
            await conn.execute("INSERT INTO widgets (id) VALUES (1)")
            got = await conn.execute("SELECT label FROM widgets WHERE id = 1")
            if got["rows"][0]["label"] != "hi":
                bad.append(f"the loaded column default should apply on migrate: {got}")
        return bad

    return asyncio.run(_run())


def _probe_cutover():
    """Zero-downtime cutover (section 9.1): the phases advance in order with reads switching at
    promotion; cutover_plan orders tables by foreign key; copy_batch_query reads a resumable batch;
    and a bulk transfer plus a mirror write are driven between two real SQLite databases."""
    from honest_persist import (
        bulk_copy_table,
        copy_batch_query,
        cutover_advance,
        cutover_phases,
        cutover_plan,
        cutover_read_target,
        mirror_write,
    )

    async def _run():
        bad = []

        # The phase machine: ordered phases, advance to terminal, reads switch at promotion.
        if cutover_phases() != ["bulk_transfer", "mirror", "promote", "detach"]:
            bad.append(f"cutover_phases wrong: {cutover_phases()}")
        if [cutover_advance(p) for p in ("bulk_transfer", "mirror", "promote", "detach")] != ["mirror", "promote", "detach", "detach"]:
            bad.append("cutover_advance should step through the phases, detach terminal")
        if [cutover_read_target(p) for p in ("bulk_transfer", "mirror", "promote", "detach")] != ["source", "source", "destination", "destination"]:
            bad.append("cutover_read_target should read the source until promotion, the destination after")

        # cutover_plan orders referenced tables before their referrers; a cycle falls back to order.
        schema = {"orders": {"columns": {"id": {"type": "integer"}, "buyer": {"references": "users.id"}}}, "users": {"columns": {"id": {"type": "integer"}}}}
        if cutover_plan(schema) != ["users", "orders"]:
            bad.append(f"cutover_plan should copy referenced tables first: {cutover_plan(schema)}")
        cyclic = {"a": {"columns": {"x": {"references": "b.y"}}}, "b": {"columns": {"y": {"references": "a.x"}}}}
        if cutover_plan(cyclic) != ["a", "b"]:
            bad.append(f"cutover_plan should fall back to declared order on a cycle: {cutover_plan(cyclic)}")
        # A reference to a table outside the schema is not an ordering constraint.
        external = {"t": {"columns": {"id": {"type": "integer"}, "ref": {"references": "outside.id"}}}}
        if cutover_plan(external) != ["t"]:
            bad.append(f"cutover_plan should ignore a reference to a table outside the schema: {cutover_plan(external)}")

        # copy_batch_query: first batch has no cursor, later batches read past the last key.
        if copy_batch_query("t", "id", None, 100) != {"sql": "SELECT * FROM t ORDER BY id LIMIT :limit", "params": {"limit": 100}}:
            bad.append(f"copy_batch_query (first) wrong: {copy_batch_query('t', 'id', None, 100)}")
        if copy_batch_query("t", "id", 42, 100) != {"sql": "SELECT * FROM t WHERE id > :after ORDER BY id LIMIT :limit", "params": {"after": 42, "limit": 100}}:
            bad.append(f"copy_batch_query (resume) wrong: {copy_batch_query('t', 'id', 42, 100)}")

        # bulk transfer between two real SQLite databases, in resumable batches.
        source = _SqliteConn()
        dest = _SqliteConn()
        await source.execute("CREATE TABLE nums (id INTEGER PRIMARY KEY, v TEXT)")
        await dest.execute("CREATE TABLE nums (id INTEGER PRIMARY KEY, v TEXT)")
        for n in (1, 2, 3):
            await source.execute("INSERT INTO nums (id, v) VALUES (:id, :v)", {"id": n, "v": "r" + str(n)})
        copied = await bulk_copy_table("nums", ["id", "v"], "id", source, dest, 2)
        moved = await dest.execute("SELECT id, v FROM nums ORDER BY id")
        if copied != 3 or [row["v"] for row in moved["rows"]] != ["r1", "r2", "r3"]:
            bad.append(f"bulk_copy_table should copy every row in batches: copied={copied}, dest={moved}")

        # mirror write reaches both databases.
        write = {"sql": "INSERT INTO nums (id, v) VALUES (:id, :v)", "params": {"id": 9, "v": "mir"}}
        results = await mirror_write(write, source, dest)
        both = []
        for conn in (source, dest):
            got = await conn.execute("SELECT v FROM nums WHERE id = 9")
            both.append(got["rows"][0]["v"] if got["rows"] else None)
        if "source" not in results or "destination" not in results or both != ["mir", "mir"]:
            bad.append(f"mirror_write should return both the source and destination results: {results}, {both}")
        return bad

    return asyncio.run(_run())


def _probe_django_loader():
    """Django interop (section 2): load_schema_from_django reads Django model definitions to a Schema
    — field types mapped to abstract SQL types, nullability, primary keys, uniqueness, choices as enum
    values, foreign-key references by db column, and defaults — and the loaded schema migrates to real
    SQLite."""
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"], DATABASES={})
        django.setup()
    from django.db import models

    from honest_persist import migrate
    from honest_persist.django_loader import load_schema_from_django

    class Customer(models.Model):
        name = models.CharField(max_length=50, unique=True)

        class Meta:
            app_label = "shop"

    class Order(models.Model):
        status = models.CharField(max_length=20, choices=[("pending", "P"), ("shipped", "S")], default="pending")
        qty = models.IntegerField(default=5)
        active = models.BooleanField(default=True)
        note = models.TextField(null=True)
        customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

        class Meta:
            app_label = "shop"

    bad = []
    order = load_schema_from_django(Customer, Order).get("shop_order", {}).get("columns", {})
    expected = {
        "id": {"type": "integer", "nullable": False, "primary_key": True},
        "status": {"type": "text", "nullable": False, "literal_values": ["pending", "shipped"], "default": "'pending'"},
        "qty": {"type": "integer", "nullable": False, "default": "5"},
        "active": {"type": "boolean", "nullable": False, "default": "TRUE"},
        "note": {"type": "text", "nullable": True},
        "customer_id": {"type": "integer", "nullable": False, "references": "shop_customer.id"},
    }
    if set(order) != set(expected):
        bad.append(f"load_schema_from_django should map every field by db column: {sorted(order)}")
    for column_name, exp in expected.items():
        if order.get(column_name) != exp:
            bad.append(f"django column {column_name}: got {order.get(column_name)}, expected {exp}")

    async def _run():
        conn = _SqliteConn()
        applied = await migrate(load_schema_from_django(Customer), conn, "sqlite")
        if "ok" not in applied:
            bad.append(f"a Django-loaded schema should migrate: {applied}")
        else:
            await conn.execute("INSERT INTO shop_customer (id, name) VALUES (1, 'acme')")
            got = await conn.execute("SELECT name FROM shop_customer WHERE id = 1")
            if got["rows"][0]["name"] != "acme":
                bad.append(f"the Django-loaded table should accept a row: {got}")
        return bad

    return asyncio.run(_run())


def _probe_deps():
    """Operation dependency ordering (section 5.4): the _DEPENDS_ON / _MUST_PRECEDE rule tables, the
    relatedness test, build_dependencies, and topological_sort (order, deterministic tie-break, cycle)."""
    from honest_persist.deps import _related, _runs_before, _subject, build_dependencies, topological_sort
    from honest_persist.types import operation

    bad = []
    # Every _DEPENDS_ON rule: the dependency runs before the dependent (same table -> related), and not
    # the reverse — so emptying/swapping a rule-table entry now fails.
    depends_on = [("add_foreign_key", "create_table"), ("add_column", "create_table"), ("add_index", "create_table"), ("add_index", "add_column"), ("add_constraint", "create_table"), ("add_constraint", "add_column"), ("create_trigger", "create_table")]
    for dependent, dependency in depends_on:
        before, after = operation(dependency, "t", {}), operation(dependent, "t", {})
        if not _runs_before(before, after):
            bad.append(f"{dependency} must run before {dependent}")
        if _runs_before(after, before):
            bad.append(f"{dependent} must not run before {dependency}")
    # create_view depends on a create_table AND on another create_view it declares (the second
    # dependency in the create_view rule): the depended-on view must run first.
    base_view = operation("create_view", "", {"view": "base"})
    derived_view = operation("create_view", "", {"view": "derived", "depends_on": ["base"]})
    if not _runs_before(base_view, derived_view):
        bad.append("a view that depends on another view must run after it")
    # ...and on the table it reads (the first dependency in the create_view rule).
    view_on_table = operation("create_view", "", {"view": "v", "depends_on": ["t"]})
    if not _runs_before(operation("create_table", "t", {}), view_on_table):
        bad.append("a view that depends on a table must run after the table is created")
    # Every _MUST_PRECEDE rule: the drop runs before the table/column drop.
    must_precede = [("drop_foreign_key", "drop_table"), ("drop_foreign_key", "drop_column"), ("drop_index", "drop_table"), ("drop_index", "drop_column"), ("drop_constraint", "drop_table"), ("drop_constraint", "drop_column"), ("drop_column", "drop_table"), ("drop_view", "drop_table"), ("drop_trigger", "drop_table")]
    for early, late in must_precede:
        if not _runs_before(operation(early, "t", {}), operation(late, "t", {})):
            bad.append(f"{early} must run before {late}")

    # _related's three branches: same table, a foreign-key reference, and a depends_on declaration.
    _subject_view = operation("create_view", "", {"view": "v", "depends_on": ["t"]})
    if _subject(_subject_view) != "v":
        bad.append("_subject should prefer the view name over the table")
    if _subject(operation("create_trigger", "tbl", {"trigger": "tg"})) != "tg":
        bad.append("_subject should prefer the trigger name over the table")
    if _subject(operation("create_function", "", {"function": "fn"})) != "fn":
        bad.append("_subject should prefer the function name")
    if _subject(operation("add_column", "tbl", {"column": "c"})) != "tbl":
        bad.append("_subject falls back to the table when there is no named object")
    if not _related(operation("add_foreign_key", "t", {"references": "o.id"}), operation("create_table", "o", {})):
        bad.append("a foreign-key reference should relate to the referenced table")
    if _related(operation("add_foreign_key", "t", {"references": "o.id"}), operation("create_table", "x", {})):
        bad.append("a foreign key must relate only to the table it actually references, not any table")
    if not _related(_subject_view, operation("create_table", "t", {})):
        bad.append("a depends_on declaration should relate to the named object")
    if _related(operation("add_column", "t", {}), operation("create_table", "u", {})):
        bad.append("unrelated operations on different tables must not relate")

    # build_dependencies + topological_sort: create_table before add_foreign_key, deterministic order.
    ops = [operation("add_foreign_key", "t", {"references": "o.id"}), operation("create_table", "t", {}), operation("create_table", "o", {})]
    deps = build_dependencies(ops)
    if sorted(deps[0]) != [1, 2] or deps[1] != [] or deps[2] != []:
        bad.append(f"add_foreign_key (index 0) should depend on both create_tables: {deps}")
    order = topological_sort(ops, deps)
    if order != [1, 2, 0]:
        bad.append(f"topological_sort should run the create_tables first, ties by index: {order}")
    # Deterministic tie-break (ready.sort()): when finishing node 1 frees node 0, the lower index 0
    # must come before the already-ready higher index 2 — [1, 0, 2], not [1, 2, 0].
    tie = [object(), object(), object()]  # three opaque nodes; order is by index only
    if topological_sort(tie, {0: [1], 1: [], 2: []}) != [1, 0, 2]:
        bad.append(f"topological_sort should break ties by index deterministically: {topological_sort(tie, {0: [1], 1: [], 2: []})}")
    # A two-node cycle has no valid order.
    cyclic = [operation("create_view", "", {"view": "a", "depends_on": ["b"]}), operation("create_view", "", {"view": "b", "depends_on": ["a"]})]
    if topological_sort(cyclic, build_dependencies(cyclic)) is not None:
        bad.append("a dependency cycle should have no topological order")
    return bad


def _probe_types_defaults():
    """host_defaults.default_sql (section 2.3) renders a Python default to its SQL literal by type, and
    diff_result (section 4.7) assembles the four-key result. Both pure."""
    from honest_persist.host_defaults import default_sql
    from honest_persist.types import diff_result

    bad = []
    cases = [("ada", "'ada'"), (True, "TRUE"), (False, "FALSE"), (3, "3"), (1.5, "1.5"), (None, None), ([1], None)]
    for value, expected in cases:
        if default_sql(value) != expected:
            bad.append(f"default_sql({value!r}) should be {expected!r}: {default_sql(value)!r}")

    result = diff_result(["op"], {"a": ["b"]}, [0], ["amb"])
    if result != {"operations": ["op"], "dependencies": {"a": ["b"]}, "execution_order": [0], "ambiguities": ["amb"]}:
        bad.append(f"diff_result should assemble the four-key result exactly: {result}")
    return bad


def run():
    groups = [
        verify_laws(HP_LAWS, [(p[0] + "->" + p[1], p) for p in _PAIRS]),
        verify_laws(RENDER_LAWS, [(op[0], op) for op in _RENDER_OPS]),
    ]
    probes = {
        "apply": _probe_apply(),
        "instrumented_apply": _probe_instrumented_apply(),
        "pool": _probe_pool(),
        "pool_registry": _probe_pool_registry(),
        "lifecycle": _probe_lifecycle(),
        "ephemeral": _probe_ephemeral(),
        "pool_events": _probe_pool_events(),
        "write_queue": _probe_write_queue(),
        "supervisor": _probe_supervisor(),
        "drain_loop": _probe_drain_loop(),
        "connection_pool": _probe_connection_pool(),
        "connect_retry": _probe_connect_retry(),
        "migrate": _probe_migrate(),
        "abstractions": _probe_abstractions(),
        "arrays_maps": _probe_arrays_maps(),
        "hierarchy": _probe_hierarchy(),
        "enums": _probe_enums(),
        "loader": _probe_loader(),
        "django_loader": _probe_django_loader(),
        "cutover": _probe_cutover(),
        "check": _probe_check(),
        "enforce_checks": _probe_enforce_checks(),
        "diff_alter": _probe_diff_alter(),
        "validate": _probe_validate(),
        "extended": _probe_extended(),
        "checked": _probe_checked(),
        "execute": _probe_execute(),
        "transaction": _probe_transaction(),
        "instrument": _probe_instrument(),
        "instrumented": _probe_instrumented(),
        "types_defaults": _probe_types_defaults(),
        "deps": _probe_deps(),
    }
    violations = [v for g in groups for v in g["violations"]]
    for name, messages in probes.items():
        if messages:
            violations.append({"law": "HP-probe", "statement": name, "subject": name, "messages": messages})

    probe_passed = sum(1 for m in probes.values() if not m)
    passed = sum(g["passed"] for g in groups) + probe_passed
    total = sum(g["total"] for g in groups) + len(probes)

    for v in violations:
        print(f"FAIL {v['law']} [{v['subject']}]: {v['messages']}")
    print(f"HP laws: {passed} passed, {len(violations)} failed, {total} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())
