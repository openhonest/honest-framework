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

import copy

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

    def execute(self, sql):
        self.executed.append(sql)

    def pause_push(self):
        self.paused += 1

    def resume_push(self):
        self.resumed += 1


class _BareConn:
    """A connection without sync-push hooks (the hasattr-false path)."""

    def __init__(self):
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)


class _FailingConn:
    def __init__(self, fail_on):
        self.executed = []
        self._fail_on = fail_on

    def pause_push(self):
        pass

    def resume_push(self):
        pass

    def execute(self, sql):
        if self._fail_on in sql:
            raise RuntimeError(f"boom on {self._fail_on}")
        self.executed.append(sql)


# --------------------------------------------------------------------------- apply boundary probes

# A column type change forces a table rebuild on sqlite/turso (section 5.5).
_RECON_CURRENT = {"t": {"columns": {"id": {"type": "uuid", "nullable": False}, "keep": {"type": "text"}}}}
_RECON_TARGET = {"t": {"columns": {"id": {"type": "text", "nullable": False}, "keep": {"type": "text"}}, "indexes": {"ix": {"columns": ["keep"]}}}}


def _probe_apply():
    bad = []
    plan = diff(_RECON_CURRENT, _RECON_TARGET)

    full = _Conn()
    result = apply(plan, _RECON_TARGET, full, "sqlite")
    joined = " ; ".join(full.executed)
    if not result["success"] or "INSERT INTO" not in joined or "CREATE" not in joined:
        bad.append(f"reconstruction did not copy data / recreate index: {full.executed}")
    if full.paused < 1 or full.resumed < 1:
        bad.append("reconstruction did not pause/resume sync push")

    bare = _BareConn()
    if not apply(plan, _RECON_TARGET, bare, "sqlite")["success"]:
        bad.append("reconstruction failed on a connection without push hooks")

    failing = _FailingConn("DROP TABLE")
    if apply(plan, _RECON_TARGET, failing, "sqlite")["success"]:
        bad.append("reconstruction should report failure when a statement raises")

    # Two reconstruction ops on one table reconstruct it once (the already-done skip).
    two = {"t": {"columns": {"id": {"type": "text"}, "keep": {"type": "integer"}}}}
    plan2 = diff(_RECON_CURRENT, two)
    conn2 = _Conn()
    apply(plan2, two, conn2, "sqlite")

    # An unknown operation has no renderer: apply must report it, not silently skip.
    unknown_plan = {"operations": [operation("frobnicate", "t", {})], "execution_order": [0], "ambiguities": [], "dependencies": {}}
    if apply(unknown_plan, {"t": {"columns": {}}}, _Conn(), "postgresql")["success"]:
        bad.append("apply should fail on an operation with no renderer")

    # A normal (non-reconstruction) DDL that raises halts apply.
    add_plan = diff({}, {"t": {"columns": {"id": {"type": "text"}}}})
    if apply(add_plan, {"t": {"columns": {"id": {"type": "text"}}}}, _FailingConn("CREATE TABLE"), "postgresql")["success"]:
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


def _probe_guards():
    """The Guard Expression DSL (§7.5): constructors validate at construction; validate_guard
    walks the closed kind sets + registry; instantiate resolves param templates; provenance
    classifies terms."""
    from honest_persist.guards import (
        GuardError,
        and_,
        column,
        compare,
        count,
        derive,
        exists,
        instantiate,
        literal,
        lookup,
        match,
        not_,
        or_,
        param,
        provenance,
        slot,
        truthy,
        validate_guard,
    )

    bad = []

    # Term + predicate constructors produce the right kind; literal accepts every scalar.
    scalars = [literal(None), literal("a"), literal(1), literal(1.5), literal(True)]
    if any(t["kind"] != "literal" for t in scalars):
        bad.append("literal scalar construction wrong")
    kinds = {
        "column": column("c"), "slot": slot("s"), "derive": derive("d"), "lookup": lookup("l"),
        "count": count("t"), "param": param("p"), "and": and_(truthy()), "or": or_(truthy()),
        "not": not_(truthy()), "compare": compare(column("c"), "=", literal(1)),
        "exists": exists("t", [match("c", literal(1))]), "true": truthy(),
    }
    for expected, node in kinds.items():
        if node["kind"] != expected:
            bad.append(f"constructor for {expected!r} produced {node['kind']!r}")

    # Construction-time errors.
    errors = [
        ("non-scalar literal", lambda: literal([1])),
        ("empty and", lambda: and_()),
        ("empty or", lambda: or_()),
        ("bad compare op", lambda: compare(column("c"), "bogus", literal(1))),
    ]
    for label, thunk in errors:
        try:
            thunk()
            bad.append(f"{label} should raise GuardError")
        except GuardError:
            pass

    # Provenance — fixed for six kinds, chain-traced for slot.
    prov = {
        "constant": literal(1), "target_snapshot": column("c"),
        "in_transaction_derivation": derive("d"), "transaction_snapshot": count("t"),
        "chain_traced": slot("s"),
    }
    for cls, term in prov.items():
        if provenance(term) != cls:
            bad.append(f"provenance({term['kind']}) != {cls}")
    if provenance(lookup("l")) != "transaction_snapshot":
        bad.append("provenance(lookup) wrong")

    # validate_guard — a fully-featured valid guard over a registry.
    registry = {"derive": {"session_actor"}, "lookup": {"role_of"}}
    good = and_(
        compare(lookup("role_of", [slot("token")]), "=", literal("owner")),
        not_(or_(
            compare(column("x"), ">", literal(0)),
            exists("t", [match("c", derive("session_actor", [slot("token")]))]),
        )),
        compare(count("t", [match("c", literal(1))]), ">", literal(0)),
        compare(param("token"), "=", literal(1)),
    )
    if "ok" not in validate_guard(good, registry):
        bad.append(f"valid guard rejected: {validate_guard(good, registry)}")
    # Rejections: unregistered name, unknown predicate kind, unknown term kind, bad op at
    # validate level, and the registry=None default (any derive fails).
    rejects = [
        ("unregistered lookup", compare(lookup("nope"), "=", literal(1)), registry),
        ("unknown predicate kind", {"kind": "bogus"}, registry),
        ("unknown term kind", compare({"kind": "weird"}, "=", literal(1)), registry),
        ("bad op at validate", {"kind": "compare", "op": "bogus", "left": literal(1), "right": literal(1)}, registry),
        ("derive with no registry", compare(derive("d"), "=", literal(1)), None),
    ]
    for label, guard, reg in rejects:
        if "err" not in validate_guard(guard, reg):
            bad.append(f"{label} should be invalid_guard")

    # instantiate — a template's param leaves are replaced; an unbound param faults.
    template = and_(
        compare(derive("session_actor", [param("token")]), "=", literal("owner")),
        not_(exists("t", [match("c", param("uid"))])),
        or_(compare(count("t", [match("c", param("n"))]), ">", literal(0)), truthy()),
    )
    resolved = instantiate(template, {"token": slot("token"), "uid": column("uid"), "n": literal(5)})
    if "ok" not in resolved:
        bad.append(f"instantiate failed: {resolved}")
    if "err" not in instantiate(compare(param("missing"), "=", literal(1)), {}):
        bad.append("unbound param should fault")
    return bad


def _probe_guard_compile():
    """Guard + guarded-mutation compilation (§7.5): the guard tree -> a SQL boolean, and the
    mutation -> a single atomic statement fusing target and guard."""
    from honest_persist import compile_guarded_mutation
    from honest_persist.guards import (
        GuardError,
        and_,
        column,
        compare,
        compile_guard,
        count,
        derive,
        exists,
        literal,
        lookup,
        match,
        not_,
        or_,
        param,
        slot,
        truthy,
    )

    bad = []
    registry = {
        "derive": {"session_actor": {"sql": "(SELECT user_id FROM sessions WHERE token = {0})"}},
        "lookup": {"role_of": {"sql": "(SELECT role FROM perm WHERE uid = {0} AND tid = {1})"}},
    }

    # literal + column compare, with the param namespace.
    sql, params = compile_guard(compare(column("status"), "=", literal("active")))
    if sql != "status = :g0" or params != {"g0": "active"}:
        bad.append(f"literal/column compare wrong: {sql} {params}")

    # every compare op maps to its SQL operator.
    op_sql = {"=": "=", "!=": "<>", "<": "<", "<=": "<=", ">": ">", ">=": ">=", "in": "IN", "not_in": "NOT IN"}
    for op, rendered in op_sql.items():
        fragment, _ = compile_guard(compare(column("a"), op, literal(1)))
        if f" {rendered} " not in fragment:
            bad.append(f"compare op {op!r} should render {rendered!r}: {fragment}")

    # and / or / not / true composition.
    composed, _ = compile_guard(and_(compare(column("a"), "=", literal(1)), or_(compare(column("b"), "=", literal(2)), not_(truthy()))))
    if not all(token in composed for token in ("AND", "OR", "NOT", "1 = 1")):
        bad.append(f"boolean composition wrong: {composed}")

    # slot bound vs unbound.
    _, slot_params = compile_guard(compare(column("uid"), "=", slot("actor")), bindings={"actor": 7})
    if slot_params.get("g0") != 7:
        bad.append(f"bound slot wrong: {slot_params}")
    for label, term in [("unbound slot", slot("missing")), ("param leaf", param("p"))]:
        try:
            compile_guard(compare(column("uid"), "=", term))
            bad.append(f"{label} should raise GuardError")
        except GuardError:
            pass

    # derive + lookup expand to their registered subqueries.
    expanded, _ = compile_guard(
        compare(lookup("role_of", [derive("session_actor", [slot("tok")]), column("tid")]), "=", literal("owner")),
        registry, {"tok": "abc"},
    )
    if "SELECT role FROM perm" not in expanded or "SELECT user_id FROM sessions" not in expanded:
        bad.append(f"derive/lookup expansion wrong: {expanded}")

    # count + exists, with and without a where-clause (the _matches_sql branches).
    counted, _ = compile_guard(compare(count("perm", [match("tid", literal("x"))]), ">", literal(1)))
    if "(SELECT COUNT(*) FROM perm WHERE tid = " not in counted:
        bad.append(f"count subquery wrong: {counted}")
    bare_count, _ = compile_guard(compare(count("perm"), ">", literal(0)))
    if "(SELECT COUNT(*) FROM perm)" not in bare_count:
        bad.append(f"count empty-where wrong: {bare_count}")
    if compile_guard(exists("perm"))[0] != "EXISTS (SELECT 1 FROM perm)":
        bad.append("exists empty-where wrong")
    if compile_guard(exists("perm", [match("uid", literal(1))]))[0] != "EXISTS (SELECT 1 FROM perm WHERE uid = :g0)":
        bad.append("exists with-where wrong")

    # guarded mutation: update / delete / insert.
    guard = compare(column("role"), "=", literal("owner"))
    update_sql, update_params = compile_guarded_mutation(
        {"target": {"table": "perm", "key": {"uid": 1, "tid": 2}}, "guard": guard, "update": {"kind": "set", "values": {"role": "ro"}}, "op": "update"}
    )
    if not update_sql.startswith("UPDATE perm SET role = :u_role WHERE") or "uid = :k_uid" not in update_sql or "(role = :g0)" not in update_sql:
        bad.append(f"update mutation wrong: {update_sql}")
    if update_params != {"g0": "owner", "u_role": "ro", "k_uid": 1, "k_tid": 2}:
        bad.append(f"update params wrong: {update_params}")
    delete_sql, _ = compile_guarded_mutation(
        {"target": {"table": "perm", "key": {"uid": 1}}, "guard": guard, "update": {"kind": "delete_row"}, "op": "delete"}
    )
    if not delete_sql.startswith("DELETE FROM perm WHERE uid = :k_uid AND (role"):
        bad.append(f"delete mutation wrong: {delete_sql}")
    insert_sql, _ = compile_guarded_mutation(
        {"target": {"table": "perm"}, "guard": guard, "update": {"kind": "insert_row", "values": {"uid": 1, "role": "owner"}}, "op": "insert"}
    )
    if not insert_sql.startswith("INSERT INTO perm (uid, role) SELECT :u_uid, :u_role WHERE (role"):
        bad.append(f"insert mutation wrong: {insert_sql}")
    return bad


class _GuardConn:
    """A fake connection for the guarded-mutation boundary: returns a canned rows_affected for
    the mutation, canned row-lists for the successive diagnosis SELECTs, or raises a driver
    error tagged with a `kind`. Test fixture — not linted."""

    def __init__(self, dialect="postgresql", rows_affected=1, returned=None, select_rows=None, raise_kind=None):
        self.dialect = dialect
        self._rows_affected = rows_affected
        self._returned = returned
        self._select_rows = list(select_rows or [])
        self._raise_kind = raise_kind
        self.executed = []

    def execute(self, sql, params):
        self.executed.append(sql)
        if sql.startswith("SELECT"):
            return {"rows": self._select_rows.pop(0) if self._select_rows else []}
        if self._raise_kind is not None:
            exc = RuntimeError("driver error")
            if self._raise_kind in ("serialization", "constraint"):
                exc.kind = self._raise_kind
            raise exc
        return {"rows_affected": self._rows_affected, "returned": self._returned}


def _probe_guarded_mutation():
    """The guarded-mutation I/O boundary (§7.5): execute, 0-rows -> guard_failed with the
    failing clause, and the serialization/constraint fault mapping."""
    from honest_persist.guards import and_, column, compare, literal
    from honest_persist.mutation import guarded_mutation

    bad = []
    g_and = and_(compare(column("role"), "=", literal("owner")), compare(column("n"), ">", literal(1)))
    g_one = compare(column("role"), "=", literal("owner"))
    target = {"table": "perm", "key": {"uid": 1}}
    update = {"kind": "set", "values": {"role": "ro"}}

    def mut(guard):
        return {"target": target, "guard": guard, "update": update, "op": "update"}

    # Success: rows affected -> ok with the returned row.
    result = guarded_mutation(mut(g_one), _GuardConn(rows_affected=1, returned={"id": 1}))
    if "ok" not in result or result["ok"]["rows_affected"] != 1 or result["ok"]["returned"] != {"id": 1}:
        bad.append(f"success wrong: {result}")

    # guard_failed, top-level AND, second operand fails (diagnosis names index 1).
    result = guarded_mutation(mut(g_and), _GuardConn(rows_affected=0, select_rows=[[1], []]))
    if result.get("err", {}).get("code") != "guard_failed" or result["err"]["detail"]["which"]["index"] != 1:
        bad.append(f"guard_failed AND diagnosis wrong: {result}")

    # guard_failed, single (non-AND) guard -> index 0.
    result = guarded_mutation(mut(g_one), _GuardConn(rows_affected=0, select_rows=[[]]))
    if result["err"]["detail"]["which"]["index"] != 0:
        bad.append(f"guard_failed single diagnosis wrong: {result}")

    # guard_failed but every clause still holds -> the target row itself is gone (index None),
    # for both a top-level AND and a single guard.
    result = guarded_mutation(mut(g_and), _GuardConn(rows_affected=0, select_rows=[[1], [1]]))
    if result["err"]["detail"]["which"]["index"] is not None:
        bad.append(f"AND target-fallback diagnosis wrong: {result}")
    result = guarded_mutation(mut(g_one), _GuardConn(rows_affected=0, select_rows=[[1]]))
    if result["err"]["detail"]["which"]["index"] is not None:
        bad.append(f"single-guard target-fallback diagnosis wrong: {result}")

    # An insert guard_failed exercises diagnosis with no target key.
    insert = {"target": {"table": "perm"}, "guard": g_one, "update": {"kind": "insert_row", "values": {"uid": 1}}, "op": "insert"}
    result = guarded_mutation(insert, _GuardConn(rows_affected=0, select_rows=[[]]))
    if result["err"]["detail"]["which"]["index"] != 0:
        bad.append(f"insert guard_failed wrong: {result}")

    # Driver faults map by kind; an unknown error re-raises rather than being swallowed.
    if guarded_mutation(mut(g_one), _GuardConn(raise_kind="serialization"))["err"]["code"] != "serialization_conflict":
        bad.append("serialization fault not mapped")
    if guarded_mutation(mut(g_one), _GuardConn(raise_kind="constraint"))["err"]["code"] != "constraint_violation":
        bad.append("constraint fault not mapped")
    try:
        guarded_mutation(mut(g_one), _GuardConn(raise_kind="unknown"))
        bad.append("an unknown driver error should re-raise")
    except RuntimeError:
        pass

    # A connection without a declared dialect falls back to the default.
    no_dialect = type("_ND", (), {"execute": lambda self, sql, params: {"rows_affected": 1, "returned": None}})()
    if "ok" not in guarded_mutation(mut(g_one), no_dialect):
        bad.append("dialect-less connection should use the default dialect")
    return bad


def _const_actor(data, *args):
    return 1


def _const_roles(data, *args):
    return ("owner", "ro")


def _probe_evaluate():
    """In-memory guard evaluation + run_action (honest-test §5.4/§5.6 dependency): the guard
    grammar evaluated over an in-memory data state, and a guarded mutation applied to it."""
    from honest_persist.evaluate import evaluate_guard, run_action
    from honest_persist.guards import (
        and_,
        column,
        compare,
        count,
        derive,
        exists,
        literal,
        lookup,
        match,
        not_,
        or_,
        param,
        slot,
        truthy,
    )
    from honest_persist.guards import GuardError

    bad = []
    data = {"perm": [{"uid": 1, "tid": 9, "role": "owner"}, {"uid": 2, "tid": 9, "role": "ro"}]}
    row = data["perm"][0]
    registry = {"derive": {"actor": _const_actor}, "lookup": {"roles": _const_roles}}

    # Every compare operator over a column.
    for op, value, expected in [("=", "owner", True), ("!=", "ro", True), ("<", "z", True), ("<=", "owner", True), (">", "a", True), (">=", "owner", True)]:
        if evaluate_guard(compare(column("role"), op, literal(value)), row, data) is not expected:
            bad.append(f"compare {op!r} wrong")
    # in / not_in against a lookup that returns a collection.
    if not evaluate_guard(compare(column("role"), "in", lookup("roles")), row, data, registry=registry):
        bad.append("'in' wrong")
    if evaluate_guard(compare(column("role"), "not_in", lookup("roles")), row, data, registry=registry):
        bad.append("'not_in' wrong")
    # and / or / not / true.
    if not evaluate_guard(and_(compare(column("role"), "=", literal("owner")), or_(truthy(), compare(column("uid"), "=", literal(99))), not_(compare(column("uid"), "=", literal(99)))), row, data):
        bad.append("boolean composition wrong")
    # count + exists over the data state.
    if not evaluate_guard(compare(count("perm", [match("tid", literal(9)), match("role", literal("owner"))]), "=", literal(1)), row, data):
        bad.append("count wrong")
    if not evaluate_guard(exists("perm", [match("uid", literal(2))]), row, data) or evaluate_guard(exists("perm", [match("uid", literal(99))]), row, data):
        bad.append("exists wrong")
    # derive term via the registry; slot bound; unbound slot and param raise.
    if not evaluate_guard(compare(derive("actor"), "=", literal(1)), row, data, registry=registry):
        bad.append("derive wrong")
    if not evaluate_guard(compare(column("uid"), "=", slot("u")), row, data, bindings={"u": 1}):
        bad.append("slot wrong")
    for term in [slot("missing"), param("p")]:
        try:
            evaluate_guard(compare(column("uid"), "=", term), row, data)
            bad.append(f"{term['kind']} term should raise GuardError")
        except GuardError:
            pass

    # run_action — the canonical orphan prevention: demoting the sole owner is refused.
    sole_owner_demote = {
        "target": {"table": "perm", "key": {"uid": 1, "tid": 9}},
        "guard": compare(count("perm", [match("tid", literal(9)), match("role", literal("owner"))]), ">", literal(1)),
        "update": {"kind": "set", "values": {"role": "ro"}},
        "op": "update",
    }
    if run_action(sole_owner_demote, data).get("err", {}).get("code") != "guard_failed":
        bad.append("demoting the sole owner should be guard_failed")
    if data["perm"][0]["role"] != "owner":
        bad.append("run_action mutated its input (not pure)")
    # update that holds, applies the new values to a fresh state.
    ok_update = {"target": {"table": "perm", "key": {"uid": 1}}, "guard": compare(column("role"), "=", literal("owner")), "update": {"kind": "set", "values": {"role": "ro"}}, "op": "update"}
    result = run_action(ok_update, data)
    if "ok" not in result or result["ok"]["data"]["perm"][0]["role"] != "ro":
        bad.append(f"holding update wrong: {result}")
    # update on a missing row -> guard_failed.
    if "err" not in run_action({"target": {"table": "perm", "key": {"uid": 99}}, "guard": truthy(), "update": {"kind": "set", "values": {}}, "op": "update"}, data):
        bad.append("update on a missing row should guard_fail")
    # delete that holds.
    deleted = run_action({"target": {"table": "perm", "key": {"uid": 2}}, "guard": truthy(), "update": {"kind": "delete_row"}, "op": "delete"}, data)
    if "ok" not in deleted or len(deleted["ok"]["data"]["perm"]) != 1:
        bad.append(f"delete wrong: {deleted}")
    # insert that holds, and one the guard rejects.
    inserted = run_action({"target": {"table": "perm"}, "guard": truthy(), "update": {"kind": "insert_row", "values": {"uid": 3, "tid": 9, "role": "ro"}}, "op": "insert"}, data)
    if "ok" not in inserted or len(inserted["ok"]["data"]["perm"]) != 3:
        bad.append(f"insert wrong: {inserted}")
    if "err" not in run_action({"target": {"table": "perm"}, "guard": compare(literal(1), "=", literal(2)), "update": {"kind": "insert_row", "values": {"uid": 3}}, "op": "insert"}, data):
        bad.append("a rejected insert should guard_fail")
    return bad


def run():
    groups = [
        verify_laws(HP_LAWS, [(p[0] + "->" + p[1], p) for p in _PAIRS]),
        verify_laws(RENDER_LAWS, [(op[0], op) for op in _RENDER_OPS]),
    ]
    probes = {
        "apply": _probe_apply(),
        "check": _probe_check(),
        "diff_alter": _probe_diff_alter(),
        "validate": _probe_validate(),
        "extended": _probe_extended(),
        "guards": _probe_guards(),
        "guard_compile": _probe_guard_compile(),
        "guarded_mutation": _probe_guarded_mutation(),
        "evaluate": _probe_evaluate(),
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
