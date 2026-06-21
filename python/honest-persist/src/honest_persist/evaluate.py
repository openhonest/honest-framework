"""In-memory guard evaluation and action execution (honest-test §5.4/§5.6 dependency).

`compile_guard` (guards.py) targets a live SQL backend; this is its in-memory twin. It runs
the same closed guard grammar over an in-memory data state — `{table: [row, ...]}` — so
honest-test can exhaustively enumerate guard checks and K-step action sequences over bounded
mock data, with no database. Pure: data in, a verdict or a new data state out.

`run_action` is the in-memory analog of guarded_mutation: evaluate the guard against the
target row and the data state; if it holds, apply the update and return the new state;
otherwise return `guard_failed`. The registry maps derive/lookup names to pure functions over
the data state (the in-memory counterpart of the SQL snapshot subqueries):
`registry = {"derive": {name: fn(data, *args)}, "lookup": {name: fn(data, *args)}}`.
"""

import copy
import operator

from honest_type import err, fault, ok

from honest_persist.guards import GuardError

_BINARY = {"=": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def _compare(op, left, right) -> bool:
    if op == "in":
        return left in right
    if op == "not_in":
        return left not in right
    return _BINARY[op](left, right)


def _eval_term(term, row, data, bindings, registry):
    kind = term["kind"]
    if kind == "literal":
        return term["value"]
    if kind == "column":
        return row.get(term["name"])
    if kind == "slot":
        if term["name"] not in bindings:
            raise GuardError(f"slot '{term['name']}' is not bound")
        return bindings[term["name"]]
    if kind in ("derive", "lookup"):
        scalar = registry[kind][term["name"]]
        args = [_eval_term(arg, row, data, bindings, registry) for arg in term["args"]]
        return scalar(data, *args)
    if kind == "count":
        return _count(term["source"]["table"], term["where"], row, data, bindings, registry)
    raise GuardError(f"term kind {kind!r} cannot be evaluated (param leaves must be instantiated first)")


def _row_matches(candidate, matches, row, data, bindings, registry) -> bool:
    return all(candidate.get(m["column"]) == _eval_term(m["term"], row, data, bindings, registry) for m in matches)


def _count(table, matches, row, data, bindings, registry) -> int:
    return sum(1 for candidate in data.get(table, []) if _row_matches(candidate, matches, row, data, bindings, registry))


def _eval_predicate(guard, row, data, bindings, registry) -> bool:
    kind = guard["kind"]
    if kind == "and":
        return all(_eval_predicate(o, row, data, bindings, registry) for o in guard["operands"])
    if kind == "or":
        return any(_eval_predicate(o, row, data, bindings, registry) for o in guard["operands"])
    if kind == "not":
        return not _eval_predicate(guard["operand"], row, data, bindings, registry)
    if kind == "compare":
        left = _eval_term(guard["left"], row, data, bindings, registry)
        right = _eval_term(guard["right"], row, data, bindings, registry)
        return _compare(guard["op"], left, right)
    if kind == "exists":
        table = guard["source"]["table"]
        return any(_row_matches(c, guard["where"], row, data, bindings, registry) for c in data.get(table, []))
    return True  # the trivial `true` guard


def evaluate_guard(guard, row, data, bindings=None, registry=None) -> bool:
    """Evaluate a guard against a target `row` within a data state (in-memory). Pure. `row`
    supplies `column` terms; `data` supplies `count`/`exists`; `bindings` supplies `slot`s;
    `registry` supplies `derive`/`lookup` scalar functions over the data state."""
    bindings = bindings or {}
    registry = registry or {"derive": {}, "lookup": {}}
    return _eval_predicate(guard, row, data, bindings, registry)


def _find_row(rows, key):
    for candidate in rows:
        if all(candidate.get(column) == value for column, value in key.items()):
            return candidate
    return None


def _guard_failed():
    return err(fault("guard_failed", "guard precondition not met", "client", {}))


def run_action(mutation, data, bindings=None, registry=None):
    """Apply a guarded mutation to an in-memory data state (honest-test §5.4). Returns
    ok({'data': new_state}) when the guard holds and the mutation applies, or err(guard_failed)
    when the guard rejects it (or the target row is absent). Pure — `data` is copied, never
    mutated in place. The in-memory analog of guarded_mutation."""
    table = mutation["target"]["table"]
    key = mutation["target"].get("key") or {}
    new_data = copy.deepcopy(data)
    rows = new_data.setdefault(table, [])
    op = mutation["op"]
    if op == "insert":
        candidate = dict(mutation["update"]["values"])
        if not evaluate_guard(mutation["guard"], candidate, new_data, bindings, registry):
            return _guard_failed()
        rows.append(candidate)
        return ok({"data": new_data})
    row = _find_row(rows, key)
    if row is None or not evaluate_guard(mutation["guard"], row, new_data, bindings, registry):
        return _guard_failed()
    if op == "delete":
        rows.remove(row)
        return ok({"data": new_data})
    row.update(mutation["update"]["values"])  # update
    return ok({"data": new_data})
