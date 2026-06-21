"""Guarded mutation compilation (section 7.5): the precondition and the write, fused.

`compile_guarded_mutation` is the pure half — a GuardedMutation value (target, guard, update,
op) compiled to a single parameterized statement whose WHERE fuses the target address with the
compiled guard, so the check and the change are one atomic operation (HCD: a single
`UPDATE`/`DELETE ... WHERE target AND guard`, or `INSERT ... SELECT ... WHERE guard`). Zero
rows affected then means the guard failed — there is no interleaving in which a precondition
holds for the check but not for the write.

Executing the statement (the I/O boundary `guarded_mutation`, diagnosis of which clause failed,
and the serialization/constraint fault mapping) is the boundary half, kept separate. This
module performs no I/O.

Parameter namespaces never collide: the guard uses `g*`, the target key uses `k_*`, the update
values use `u_*`.
"""

from honest_persist.guards import compile_guard
from honest_type import err, fault, ok


def _key_clause(key, params) -> str:
    """Equality conditions addressing the target row(s), recording `k_<col>` params."""
    conditions = []
    for column, value in key.items():
        name = f"k_{column}"
        params[name] = value
        conditions.append(f"{column} = :{name}")
    return " AND ".join(conditions)


def _render_update(mutation, table, guard_sql, params) -> str:
    values = mutation["update"]["values"]
    assignments = []
    for column, value in values.items():
        name = f"u_{column}"
        params[name] = value
        assignments.append(f"{column} = :{name}")
    where = " AND ".join(
        clause for clause in [_key_clause(mutation["target"].get("key") or {}, params), f"({guard_sql})"] if clause
    )
    return f"UPDATE {table} SET {', '.join(assignments)} WHERE {where}"


def _render_delete(mutation, table, guard_sql, params) -> str:
    where = " AND ".join(
        clause for clause in [_key_clause(mutation["target"].get("key") or {}, params), f"({guard_sql})"] if clause
    )
    return f"DELETE FROM {table} WHERE {where}"


def _render_insert(mutation, table, guard_sql, params) -> str:
    values = mutation["update"]["values"]
    columns = list(values)
    placeholders = []
    for column in columns:
        name = f"u_{column}"
        params[name] = values[column]
        placeholders.append(f":{name}")
    return f"INSERT INTO {table} ({', '.join(columns)}) SELECT {', '.join(placeholders)} WHERE ({guard_sql})"


_RENDERERS = {"update": _render_update, "delete": _render_delete, "insert": _render_insert}


def compile_guarded_mutation(mutation, dialect="postgresql", registry=None, bindings=None) -> tuple[str, dict]:
    """Compile a GuardedMutation to a single atomic statement and its named params (section
    7.5). Pure. The guard, target key, and update values share one params dict under
    non-colliding prefixes. `dialect` is accepted for the SQL backends, whose statement form is
    uniform (HCD); MongoDB/DynamoDB compilation is a boundary concern. `registry`/`bindings`
    are passed through to compile_guard."""
    guard_sql, params = compile_guard(mutation["guard"], registry, bindings)
    table = mutation["target"]["table"]
    sql = _RENDERERS[mutation["op"]](mutation, table, guard_sql, params)
    return sql, params


# --------------------------------------------------------------------------- the I/O boundary

# guarded_mutation performs I/O and catches at the boundary by design (Typed Exceptions at the
# Boundary). The pure compilation above is unaffected; the disable is scoped to the boundary.
# honest: disable HC-P002


def _clause_holds(table, key, clause, conn, registry, bindings) -> bool:
    """True if a single guard clause holds for the target row right now — a probe SELECT used
    only to diagnose which clause of a failed guard was the culprit."""
    clause_sql, params = compile_guard(clause, registry, bindings)
    for column, value in key.items():
        params[f"k_{column}"] = value
    key_sql = " AND ".join(f"{column} = :k_{column}" for column in key)
    where = " AND ".join(part for part in [key_sql, f"({clause_sql})"] if part)
    rows = conn.execute(f"SELECT 1 FROM {table} WHERE {where}", params)["rows"]
    return len(rows) > 0


def diagnose_guard_failure(mutation, conn, registry=None, bindings=None) -> dict:
    """Identify which sub-clause of the guard failed, so the boundary can map guard_failed to
    the right HTTP status. For a top-level `and`, probe each operand and name the first that no
    longer holds; otherwise the whole guard is the clause. `index` is None when every clause
    holds — the target row itself is absent or was changed out from under the write."""
    guard = mutation["guard"]
    table = mutation["target"]["table"]
    key = mutation["target"].get("key") or {}
    if guard["kind"] == "and":
        for index, operand in enumerate(guard["operands"]):
            if not _clause_holds(table, key, operand, conn, registry, bindings):
                return {"index": index, "clause": operand}
        return {"index": None, "clause": {"kind": "target"}}
    if not _clause_holds(table, key, guard, conn, registry, bindings):
        return {"index": 0, "clause": guard}
    return {"index": None, "clause": {"kind": "target"}}


def _classify_failure(exc):
    """Map a driver exception to a Result fault by its `kind`, or None to re-raise (an error
    honest-persist does not own must not be silently swallowed)."""
    kind = getattr(exc, "kind", None)
    if kind == "serialization":
        return err(fault("serialization_conflict", str(exc), "server", {"detail": str(exc)}))
    if kind == "constraint":
        return err(fault("constraint_violation", str(exc), "client", {"detail": str(exc)}))
    return None


def guarded_mutation(mutation, conn, registry=None, bindings=None):
    """Execute a guarded mutation atomically (section 7.5). Compiles the fused statement, runs
    it, and maps the outcome: rows affected -> ok; zero rows -> guard_failed (with the failing
    clause); a serialization or constraint driver error -> the matching Result fault. The only
    sanctioned way to mutate persisted state."""
    sql, params = compile_guarded_mutation(mutation, getattr(conn, "dialect", "postgresql"), registry, bindings)
    try:
        result = conn.execute(sql, params)
    except Exception as exc:
        classified = _classify_failure(exc)
        if classified is None:
            raise
        return classified
    if result["rows_affected"] == 0:
        which = diagnose_guard_failure(mutation, conn, registry, bindings)
        return err(fault("guard_failed", "guard precondition not met", "client", {"which": which}))
    return ok({"rows_affected": result["rows_affected"], "returned": result.get("returned")})
# honest: enable HC-P002
