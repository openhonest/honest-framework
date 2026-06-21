"""The Guard Expression DSL (section 7.5): the guard is data, not code.

A guard is a tagged-union value tree — the precondition half of a guarded mutation. Like an
honest-type vocabulary it is a closed set of node kinds, built by pure constructor functions,
statically analysable, exhaustively enumerable, and (in apply, later) compiled to a backend
atomic operation. No language's exception, lambda, or object syntax appears in a guard; a
guard is a value that can be serialised, compared, and inspected.

Two layers, both with closed kind sets:
  - predicates (boolean-valued): and / or / not / compare / exists / true
  - terms (value-valued operands): literal / column / slot / derive / lookup / count / param

Constructors validate kind and arity at construction — a malformed guard is a construction-
time error (`GuardError`), never a runtime surprise. `validate_guard` additionally checks the
closed kind sets across a whole tree and the registered derive/lookup names; `instantiate`
turns a template (with `param` leaves) into a concrete guard; `provenance` reports a term's
provenance class — the property honest-check reads to decide HC-P015.
"""

from honest_type import err, fault, ok


class GuardError(Exception):
    """A guard that cannot be built: unknown compare op, empty junction, non-scalar literal."""


_COMPARE_OPS = frozenset({"=", "!=", "<", "<=", ">", ">=", "in", "not_in"})
_PREDICATE_KINDS = frozenset({"and", "or", "not", "compare", "exists", "true"})
_TERM_KINDS = frozenset({"literal", "column", "slot", "derive", "lookup", "count", "param"})
_SCALAR_TYPES = (str, int, float, bool)  # bool is an int subclass; None is allowed separately

# Statically fixed provenance for six of the seven term kinds; slot is chain-traced (its
# soundness is decided by honest-check tracing the slot in the enclosing chain).
_PROVENANCE = {
    "literal": "constant",
    "column": "target_snapshot",
    "derive": "in_transaction_derivation",
    "lookup": "transaction_snapshot",
    "count": "transaction_snapshot",
    "slot": "chain_traced",
}


# --------------------------------------------------------------------------- term constructors


def literal(value):
    """A constant term. Value must be a scalar (string / number / boolean / null)."""
    if value is not None and not isinstance(value, _SCALAR_TYPES):  # honest: ignore HC-P005  (primitive input-contract guard, not domain dispatch)
        raise GuardError(f"literal value must be a scalar (string/number/boolean/null), got {value!r}")
    return {"kind": "literal", "value": value}


def column(name):
    """A reference to a column of the row(s) under mutation (target_snapshot provenance)."""
    return {"kind": "column", "name": name}


def slot(name):
    """A manifest slot carried into the link (chain-traced provenance — the only contextual one)."""
    return {"kind": "slot", "name": name}


def derive(name, args=None):
    """An in-transaction derivation (e.g. an AuthProvider deriving the actor from a token)."""
    return {"kind": "derive", "name": name, "args": list(args or [])}


def lookup(name, args=None):
    """A registered scalar over the current snapshot, inside the transaction (e.g. role_of)."""
    return {"kind": "lookup", "name": name, "args": list(args or [])}


def count(table, where=None):
    """An aggregate over the current snapshot, inside the transaction."""
    return {"kind": "count", "source": {"table": table}, "where": list(where or [])}


def param(name):
    """A placeholder leaf, valid only inside a GuardExpressionTemplate (resolved by instantiate)."""
    return {"kind": "param", "name": name}


def match(column_name, term):
    """A {column, term} pair for an exists/count where-clause."""
    return {"column": column_name, "term": term}


# --------------------------------------------------------------------------- predicate constructors


def and_(*operands):
    if not operands:
        raise GuardError("and() needs at least one operand")
    return {"kind": "and", "operands": list(operands)}


def or_(*operands):
    if not operands:
        raise GuardError("or() needs at least one operand")
    return {"kind": "or", "operands": list(operands)}


def not_(operand):
    return {"kind": "not", "operand": operand}


def compare(left, op, right):
    if op not in _COMPARE_OPS:
        raise GuardError(f"unknown compare op {op!r}")
    return {"kind": "compare", "left": left, "op": op, "right": right}


def exists(table, where=None):
    return {"kind": "exists", "source": {"table": table}, "where": list(where or [])}


def truthy():
    """The trivial guard. Structurally useless — honest-check flags it (HC-P018)."""
    return {"kind": "true"}


# --------------------------------------------------------------------------- provenance


def provenance(term):
    """The provenance class of a term (section 7.5). Fixed for six kinds; 'chain_traced' for
    slot. A param has no provenance until instantiated, so it is not in the table."""
    return _PROVENANCE[term["kind"]]


# --------------------------------------------------------------------------- validation


def _validate_term(term, registry, errors):
    kind = term.get("kind")
    if kind not in _TERM_KINDS:
        errors.append(f"unknown term kind {kind!r}")
        return
    if kind in ("derive", "lookup"):
        if term["name"] not in registry[kind]:
            errors.append(f"{kind} '{term['name']}' is not registered")
        for arg in term["args"]:
            _validate_term(arg, registry, errors)
    if kind == "count":
        for clause in term["where"]:
            _validate_term(clause["term"], registry, errors)


def _validate_predicate(guard, registry, errors):
    kind = guard.get("kind")
    if kind not in _PREDICATE_KINDS:
        errors.append(f"unknown predicate kind {kind!r}")
        return
    if kind in ("and", "or"):
        for operand in guard["operands"]:
            _validate_predicate(operand, registry, errors)
    if kind == "not":
        _validate_predicate(guard["operand"], registry, errors)
    if kind == "compare":
        if guard["op"] not in _COMPARE_OPS:
            errors.append(f"unknown compare op {guard['op']!r}")
        _validate_term(guard["left"], registry, errors)
        _validate_term(guard["right"], registry, errors)
    if kind == "exists":
        for clause in guard["where"]:
            _validate_term(clause["term"], registry, errors)


def validate_guard(guard, registry=None):
    """Validate a guard tree against the closed kind sets and the registered derive/lookup
    names (section 7.5). Returns ok(guard), or err(fault 'invalid_guard') listing every
    problem. Pure — it walks the value tree, never executes it. `registry` is
    {'derive': set, 'lookup': set}; absent names default to empty (any derive/lookup fails)."""
    registry = registry or {}
    registry = {"derive": frozenset(registry.get("derive", ())), "lookup": frozenset(registry.get("lookup", ()))}
    errors = []
    _validate_predicate(guard, registry, errors)
    if errors:
        return err(fault("invalid_guard", "Guard tree is malformed or references unregistered names", "server", {"errors": errors}))
    return ok(guard)


# --------------------------------------------------------------------------- instantiation


def _instantiate_term(term, bindings, errors):
    kind = term["kind"]
    if kind == "param":
        if term["name"] not in bindings:
            errors.append(f"unbound param '{term['name']}'")
            return term
        return bindings[term["name"]]
    if kind in ("derive", "lookup"):
        return {**term, "args": [_instantiate_term(arg, bindings, errors) for arg in term["args"]]}
    if kind == "count":
        return {**term, "where": [match(c["column"], _instantiate_term(c["term"], bindings, errors)) for c in term["where"]]}
    return term


def _instantiate_predicate(guard, bindings, errors):
    kind = guard["kind"]
    if kind in ("and", "or"):
        return {**guard, "operands": [_instantiate_predicate(o, bindings, errors) for o in guard["operands"]]}
    if kind == "not":
        return {**guard, "operand": _instantiate_predicate(guard["operand"], bindings, errors)}
    if kind == "compare":
        return {**guard, "left": _instantiate_term(guard["left"], bindings, errors), "right": _instantiate_term(guard["right"], bindings, errors)}
    if kind == "exists":
        return {**guard, "where": [match(c["column"], _instantiate_term(c["term"], bindings, errors)) for c in guard["where"]]}
    return guard


def instantiate(template, bindings):
    """Resolve a GuardExpressionTemplate to a concrete guard by replacing every `param` leaf
    with its binding (section 7.5). Returns ok(guard), or err(fault 'unbound_param')."""
    errors = []
    result = _instantiate_predicate(template, bindings, errors)
    if errors:
        return err(fault("unbound_param", "Template has unbound params", "server", {"errors": errors}))
    return ok(result)


# --------------------------------------------------------------------------- compilation

# Guard compare ops -> SQL operators (HCD; `<>` is the portable not-equal).
_COMPARE_SQL = {
    "=": "=", "!=": "<>", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
    "in": "IN", "not_in": "NOT IN",
}


def _bind(value, params, state) -> str:
    """Record a value as a fresh named parameter and return its `:placeholder`."""
    name = f"g{state['n']}"
    state["n"] += 1
    params[name] = value
    return f":{name}"


def _compile_term(term, params, state, registry, bindings) -> str:
    """A GuardTerm -> a SQL value expression, accumulating params. Pure given its inputs."""
    kind = term["kind"]
    if kind == "literal":
        return _bind(term["value"], params, state)
    if kind == "column":
        return term["name"]
    if kind == "slot":
        if term["name"] not in bindings:
            raise GuardError(f"slot '{term['name']}' is not bound at compile time")
        return _bind(bindings[term["name"]], params, state)
    if kind in ("derive", "lookup"):
        sql_template = registry[kind][term["name"]]["sql"]
        args = [_compile_term(arg, params, state, registry, bindings) for arg in term["args"]]
        return sql_template.format(*args)
    if kind == "count":
        return f"(SELECT COUNT(*) FROM {term['source']['table']}{_matches_sql(term['where'], params, state, registry, bindings)})"
    raise GuardError(f"term kind {kind!r} is not compilable (param leaves must be instantiated first)")


def _matches_sql(matches, params, state, registry, bindings) -> str:
    """A WHERE clause for an exists/count subquery from its [{column, term}] matches."""
    if not matches:
        return ""
    conditions = [f"{m['column']} = {_compile_term(m['term'], params, state, registry, bindings)}" for m in matches]
    return " WHERE " + " AND ".join(conditions)


def _compile_predicate(guard, params, state, registry, bindings) -> str:
    """A GuardExpression -> a SQL boolean expression, accumulating params. Pure."""
    kind = guard["kind"]
    if kind == "and":
        return "(" + " AND ".join(_compile_predicate(o, params, state, registry, bindings) for o in guard["operands"]) + ")"
    if kind == "or":
        return "(" + " OR ".join(_compile_predicate(o, params, state, registry, bindings) for o in guard["operands"]) + ")"
    if kind == "not":
        return "(NOT " + _compile_predicate(guard["operand"], params, state, registry, bindings) + ")"
    if kind == "compare":
        left = _compile_term(guard["left"], params, state, registry, bindings)
        right = _compile_term(guard["right"], params, state, registry, bindings)
        return f"{left} {_COMPARE_SQL[guard['op']]} {right}"
    if kind == "exists":
        return f"EXISTS (SELECT 1 FROM {guard['source']['table']}{_matches_sql(guard['where'], params, state, registry, bindings)})"
    return "1 = 1"  # the trivial `true` guard


def compile_guard(guard, registry=None, bindings=None) -> tuple[str, dict]:
    """Compile a guard tree to a SQL boolean expression and its named parameters (section 7.5).
    Pure: same (guard, registry, bindings) -> same (sql, params). Literals and bound slots
    become named params; columns are bare (the target row, read atomically with the write);
    derive/lookup expand to their registered snapshot subqueries; count/exists become
    aggregate/EXISTS subqueries. `registry` is {'derive': {name: {sql}}, 'lookup': {...}} whose
    sql templates use `{0}`, `{1}` for compiled args; `bindings` supplies slot values."""
    registry = registry or {"derive": {}, "lookup": {}}
    bindings = bindings or {}
    params: dict = {}
    state = {"n": 0}
    sql = _compile_predicate(guard, params, state, registry, bindings)
    return sql, params
