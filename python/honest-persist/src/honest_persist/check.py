"""CHECK constraint enforcement (section 6.2).

A declared CHECK must be enforced on every dialect. Where the engine enforces CHECK natively
it is emitted as DDL; where it does not, the expression is compiled into a pure row validator
and enforced at the write boundary. `parse_check` compiles a CHECK string into an expression
tree (the closed, finite vocabulary the guard DSL uses, section 7.5); `check_holds` evaluates
that tree against a row. A CHECK outside the supported vocabulary returns an `uncompilable_check`
fault rather than a silently dropped guarantee.

The supported vocabulary: comparisons (>, <, >=, <=, =, !=, <>), AND / OR / NOT, parentheses,
IN (literal list); terms are column names and integer / float / string literals. Pure: the
parser's cursor is a local accumulator sealed inside parse_check.
"""

import operator

from honest_type import err, fault, ok

_KEYWORDS = frozenset({"AND", "OR", "NOT", "IN"})
_COMPARE_OPS = frozenset({">", "<", ">=", "<=", "=", "!=", "<>"})
_COMPARE = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "=": operator.eq,
    "!=": operator.ne,
    "<>": operator.ne,
}


def _number(text):
    return float(text) if "." in text else int(text)


def _tokenize(expression):
    tokens = []
    index = 0
    length = len(expression)
    while index < length:
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char == "'":
            end = index + 1
            while end < length and expression[end] != "'":
                end += 1
            tokens.append({"type": "string", "value": expression[index + 1:end]})
            index = end + 1
            continue
        if char.isdigit() or (char == "-" and index + 1 < length and expression[index + 1].isdigit()):
            end = index + 1 if char == "-" else index
            while end < length and (expression[end].isdigit() or expression[end] == "."):
                end += 1
            tokens.append({"type": "number", "value": expression[index:end]})
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index
            while end < length and (expression[end].isalnum() or expression[end] == "_"):
                end += 1
            word = expression[index:end]
            kind = "keyword" if word.upper() in _KEYWORDS else "name"
            tokens.append({"type": kind, "value": word.upper() if kind == "keyword" else word})
            index = end
            continue
        two = expression[index:index + 2]
        if two in _COMPARE_OPS:
            tokens.append({"type": "op", "value": two})
            index += 2
            continue
        if char in _COMPARE_OPS or char in ("(", ")", ","):
            tokens.append({"type": "op", "value": char})
            index += 1
            continue
        tokens.append({"type": "unknown", "value": char})
        index += 1
    tokens.append({"type": "end", "value": ""})
    return tokens


def _peek(tokens, cursor):
    return tokens[cursor["pos"]]


def _advance(tokens, cursor):
    token = tokens[cursor["pos"]]
    cursor["pos"] += 1
    return token


def _parse_term(tokens, cursor):
    token = _peek(tokens, cursor)
    if token["type"] == "name":
        _advance(tokens, cursor)
        return {"kind": "column", "name": token["value"]}
    if token["type"] == "number":
        _advance(tokens, cursor)
        return {"kind": "literal", "value": _number(token["value"])}
    if token["type"] == "string":
        _advance(tokens, cursor)
        return {"kind": "literal", "value": token["value"]}
    return None


def _parse_value_list(tokens, cursor):
    if _peek(tokens, cursor)["value"] != "(":
        return None
    _advance(tokens, cursor)
    values = []
    while True:
        term = _parse_term(tokens, cursor)
        if term is None or term["kind"] != "literal":
            return None
        values.append(term)
        if _peek(tokens, cursor)["value"] != ",":
            break
        _advance(tokens, cursor)
    if _peek(tokens, cursor)["value"] != ")":
        return None
    _advance(tokens, cursor)
    return values


def _parse_comparison(tokens, cursor):
    left = _parse_term(tokens, cursor)
    if left is None:
        return None
    token = _peek(tokens, cursor)
    if token["type"] == "op" and token["value"] in _COMPARE_OPS:
        op = _advance(tokens, cursor)["value"]
        right = _parse_term(tokens, cursor)
        if right is None:
            return None
        return {"kind": "compare", "op": op, "left": left, "right": right}
    if token["value"] == "IN":
        _advance(tokens, cursor)
        values = _parse_value_list(tokens, cursor)
        if values is None:
            return None
        return {"kind": "in", "term": left, "values": values}
    return None


def _parse_primary(tokens, cursor):
    if _peek(tokens, cursor)["value"] == "(":
        _advance(tokens, cursor)
        inner = _parse_or(tokens, cursor)
        if inner is None or _peek(tokens, cursor)["value"] != ")":
            return None
        _advance(tokens, cursor)
        return inner
    return _parse_comparison(tokens, cursor)


def _parse_not(tokens, cursor):
    if _peek(tokens, cursor)["value"] == "NOT":
        _advance(tokens, cursor)
        clause = _parse_not(tokens, cursor)
        if clause is None:
            return None
        return {"kind": "not", "clause": clause}
    return _parse_primary(tokens, cursor)


def _parse_junction(tokens, cursor, keyword, kind, parse_operand):
    left = parse_operand(tokens, cursor)
    if left is None:
        return None
    clauses = [left]
    while _peek(tokens, cursor)["value"] == keyword:
        _advance(tokens, cursor)
        right = parse_operand(tokens, cursor)
        if right is None:
            return None
        clauses.append(right)
    if len(clauses) == 1:
        return left
    return {"kind": kind, "clauses": clauses}


def _parse_and(tokens, cursor):
    return _parse_junction(tokens, cursor, "AND", "and", _parse_not)


def _parse_or(tokens, cursor):
    return _parse_junction(tokens, cursor, "OR", "or", _parse_and)


def parse_check(expression):
    """Compile a CHECK expression string into an expression tree (section 6.2). Returns
    ok(tree), or err(fault 'uncompilable_check') when the expression is outside the supported
    vocabulary - never a silently dropped guarantee."""
    tokens = _tokenize(expression)
    if any(token["type"] == "unknown" for token in tokens):
        return err(fault("uncompilable_check", f"CHECK uses an unsupported token: {expression}", "server", {"expression": expression}))
    cursor = {"pos": 0}
    tree = _parse_or(tokens, cursor)
    if tree is None or _peek(tokens, cursor)["type"] != "end":
        return err(fault("uncompilable_check", f"CHECK cannot be compiled: {expression}", "server", {"expression": expression}))
    return ok(tree)


def _eval_term(term, row):
    if term["kind"] == "column":
        return row.get(term["name"])
    return term["value"]


def _eval_compare(node, row):
    return _COMPARE[node["op"]](_eval_term(node["left"], row), _eval_term(node["right"], row))


def _eval_and(node, row):
    return all(check_holds(clause, row) for clause in node["clauses"])


def _eval_or(node, row):
    return any(check_holds(clause, row) for clause in node["clauses"])


def _eval_not(node, row):
    return not check_holds(node["clause"], row)


def _eval_in(node, row):
    return _eval_term(node["term"], row) in [value["value"] for value in node["values"]]


_EVALUATORS = {
    "compare": _eval_compare,
    "and": _eval_and,
    "or": _eval_or,
    "not": _eval_not,
    "in": _eval_in,
}


def check_holds(tree, row):
    """Evaluate a compiled CHECK tree against a row (section 6.2). Pure: row -> Bool."""
    return _EVALUATORS[tree["kind"]](tree, row)
