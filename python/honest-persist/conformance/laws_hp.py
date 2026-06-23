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
import sqlite3

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


class _Conn:
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


class _BareConn:
    """A connection without sync-push hooks (the hasattr-false path)."""

    def __init__(self):
        self.executed = []

    async def execute(self, sql):
        self.executed.append(sql)


class _FailingConn:
    def __init__(self, fail_on):
        self.executed = []
        self._fail_on = fail_on

    async def pause_push(self):
        pass

    async def resume_push(self):
        pass

    async def execute(self, sql):
        if self._fail_on in sql:
            raise RuntimeError(f"boom on {self._fail_on}")
        self.executed.append(sql)


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
        if full.paused < 1 or full.resumed < 1:
            bad.append("reconstruction did not pause/resume sync push")

        bare = _BareConn()
        if not (await apply(plan, _RECON_TARGET, bare, "sqlite"))["success"]:
            bad.append("reconstruction failed on a connection without push hooks")

        failing = _FailingConn("DROP TABLE")
        if (await apply(plan, _RECON_TARGET, failing, "sqlite"))["success"]:
            bad.append("reconstruction should report failure when a statement raises")

        # Two reconstruction ops on one table reconstruct it once (the already-done skip).
        two = {"t": {"columns": {"id": {"type": "text"}, "keep": {"type": "integer"}}}}
        plan2 = diff(_RECON_CURRENT, two)
        conn2 = _Conn()
        await apply(plan2, two, conn2, "sqlite")

        # An unknown operation has no renderer: apply must report it, not silently skip.
        unknown_plan = {"operations": [operation("frobnicate", "t", {})], "execution_order": [0], "ambiguities": [], "dependencies": {}}
        if (await apply(unknown_plan, {"t": {"columns": {}}}, _Conn(), "postgresql"))["success"]:
            bad.append("apply should fail on an operation with no renderer")

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
    if checked_select(schema, "ghost").get("err", {}).get("code") != "unknown_table":
        bad.append("unknown table should fault unknown_table")
    if checked_select(schema, "users", joins=[{"table": "ghost", "on": "x"}]).get("err", {}).get("code") != "unknown_table":
        bad.append("unknown join table should fault unknown_table")
    # the unknown_column fault names the offending column(s) and the declared set.
    detail = checked_select(schema, "users", columns=["emial", "id"]).get("err", {}).get("detail", {})
    if detail.get("columns") != ["emial"] or "email" not in detail.get("declared", []):
        bad.append(f"unknown_column detail should name the bad column and the declared set: {detail}")

    # insert / update / delete: ok and unknown-column paths; the where=None branch on update and delete.
    if "ok" not in checked_insert(schema, "users", {"id": 1, "email": "a@b.co"}):
        bad.append("valid checked_insert should be ok")
    if checked_insert(schema, "users", {"nope": 1}).get("err", {}).get("code") != "unknown_column":
        bad.append("unknown insert column should fault")
    if "ok" not in checked_update(schema, "users", {"status": "active"}, {"id": 1}):
        bad.append("valid checked_update should be ok")
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
        if r.get("err", {}).get("code") != "write_failed" or r["err"]["detail"]["failed_at"] != 0:
            bad.append(f"failure should be write_failed at index 0: {r}")
        if first.log != ["begin", ("execute", w1["sql"]), "rollback"]:
            bad.append(f"rollback path should stop at the failing write: {first.log}")

        # failure on a later write: the earlier write ran, then rollback; failed_at points at it.
        middle = _TxConn(1)
        r = await transaction([w1, w2], middle)
        if r["err"]["detail"]["failed_at"] != 1 or middle.log[-1] != "rollback" or "commit" in middle.log:
            bad.append(f"mid-transaction failure should roll back at index 1: {r} log={middle.log}")
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
        extract_table,
        pool_fault,
        sql_hash,
    )

    bad = []
    if POOL_FAULT_CODES != {"unknown_database", "unresolvable_dsn", "unknown_tenant", "pool_exhausted", "pool_closed", "credential_rejected", "lifecycle_failed"}:
        bad.append("POOL_FAULT_CODES vocabulary is wrong")
    if pool_fault("unknown_database", "x")["category"] != "client":
        bad.append("unknown_database is a caller (client) error")
    if pool_fault("pool_exhausted", "x")["category"] != "server":
        bad.append("pool_exhausted is a server (capacity) error")
    if extract_table("SELECT * FROM users WHERE id = 1") != "users":
        bad.append("extract_table should find the FROM table")
    if extract_table("INSERT INTO orders (x) VALUES (1)") != "orders":
        bad.append("extract_table should find the INTO table")
    if extract_table("BEGIN") != "":
        bad.append("extract_table should return '' when no table is present")
    if sql_hash("SELECT 1") != sql_hash("SELECT 1") or sql_hash("SELECT 1") == sql_hash("SELECT 2"):
        bad.append("sql_hash should be a stable per-sql digest")
    if len(sql_hash("SELECT 1")) != 64:
        bad.append("sql_hash should be a 64-char sha256 hex digest")
    dev = build_query_event("db", "users", "select", 3, 1500, "SELECT 1", "r1", None, True)
    prod = build_query_event("db", "users", "select", 3, 1500, "SELECT 1", "r1", None, False)
    if dev["sql"] != "SELECT 1" or prod["sql"] is not None:
        bad.append("the full sql is included only in development mode")
    if dev["sql_hash"] != sql_hash("SELECT 1"):
        bad.append("the query event should always carry the sql_hash")
    migration = build_migration_event("db", "create_table", "users", {"x": 1}, 2000, "CREATE TABLE users", True, None)
    if migration["operation"] != "create_table" or migration["success"] is not True:
        bad.append("build_migration_event should carry the operation and success flag")
    pool = build_pool_event("db", "created", 10, 1, 0, None, None, None)
    if pool["event"] != "created" or pool["pool_size"] != 10:
        bad.append("build_pool_event should carry the event and pool size")
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

        # No emit wired in: run and return, no event.
        if await instrumented_execute(q, conn, None, "users_db", "select", "r1", True) != [{"id": 1}, {"id": 2}]:
            bad.append("with no emit, instrumented_execute should just return the rows")

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
        "check": _probe_check(),
        "diff_alter": _probe_diff_alter(),
        "validate": _probe_validate(),
        "extended": _probe_extended(),
        "checked": _probe_checked(),
        "execute": _probe_execute(),
        "transaction": _probe_transaction(),
        "instrument": _probe_instrument(),
        "instrumented": _probe_instrumented(),
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
