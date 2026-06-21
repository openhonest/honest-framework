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
