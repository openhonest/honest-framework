"""Deliberate fault-path generation (section 9.2): read a link's guards and construct inputs that
trigger its fault exits.

A fault exit is a point where a link returns `err`. Strategy 1 (section 9.2.1) reads the guard: for a
fault exit whose guard is a solvable comparison of a manifest field against an integer, it produces a
manifest fragment that satisfies the guard. A guard that turns on external state - it calls something
whose result no manifest can force - cannot be reached by any input and is disclosed by name, never
silently dropped (section 9.2.2). A guard that is pure over the manifest but not one strategy 1 solves
is deferred to perturbation (strategy 2). The condition is read from the code that already holds it; a
link is never asked to declare its failures a second time.
"""

from honest_parse import node_text, parse_python, walk

# Operator token -> a value that makes `manifest[field] <op> literal` true, keyed by the tree-sitter
# operator node type. Numeric comparison guards only; a value strategy 1 can solve by reading.
_TRIGGER = {
    "<=": lambda literal: literal,
    "<": lambda literal: literal - 1,
    ">=": lambda literal: literal,
    ">": lambda literal: literal + 1,
    "==": lambda literal: literal,
    "!=": lambda literal: literal + 1,
}


def _string_value(node, source) -> str:
    """The text of a string literal node with its surrounding quotes stripped."""
    return node_text(node, source)[1:-1]


def _has_call(node) -> bool:
    """Whether a guard subtree calls anything - the signal it turns on external state (section 9.2.2)."""
    return any(descendant.type == "call" for descendant in walk(node))


def _returns_err(consequence, source) -> bool:
    """Whether an if-consequence returns a dict carrying an `err` key - the shape of a fault exit."""
    return any(
        node.type == "pair" and node.child_by_field_name("key").type == "string" and _string_value(node.child_by_field_name("key"), source) == "err"
        for node in walk(consequence)
    )


def _fault_code(consequence, source) -> str:
    """The fault code an err-returning consequence carries: the first string argument of its `fault(...)`
    call, or the empty string when it returns an err with no fault call."""
    for node in walk(consequence):
        if node.type == "call" and node_text(node.child_by_field_name("function"), source) == "fault":
            for arg in node.child_by_field_name("arguments").named_children:
                if arg.type == "string":
                    return _string_value(arg, source)
    return ""


def _manifest_field(node, source):
    """The field name when `node` is `manifest["field"]`, else None."""
    if node.type != "subscript":
        return None
    key = node.child_by_field_name("subscript")
    if node_text(node.child_by_field_name("value"), source) != "manifest" or key.type != "string":
        return None
    return _string_value(key, source)


def _solved_trigger(condition, source):
    """A {field: value} fragment that makes a comparison guard true, or None when the guard is not a
    solvable comparison of `manifest["field"]` against an integer literal. A non-comparison guard is
    rejected by the shape checks below (a wrong child count, or an operator not in the trigger table),
    so it needs no separate type guard."""
    parts = condition.children
    if len(parts) != 3:
        return None
    left, operator, right = parts
    field = _manifest_field(left, source)
    if field is None or operator.type not in _TRIGGER or right.type != "integer":
        return None
    return {field: _TRIGGER[operator.type](int(node_text(right, source)))}


def _fault_ifs(source_bytes):
    """Every if_statement whose consequence returns an err fault."""
    root = parse_python(source_bytes).root_node
    return [
        node
        for node in walk(root)
        if node.type == "if_statement" and _returns_err(node.child_by_field_name("consequence"), source_bytes)
    ]


def fault_exits(source) -> dict:
    """Read a link's fault exits (section 9.2). Returns three lists: `reachable` fault exits, each with a
    trigger fragment strategy 1 solved from the guard; `deferred` fault exits, pure over the manifest but
    not solved by reading, left to perturbation (strategy 2); and `unreachable` fault exits, whose guard
    turns on external state so no input can reach them, each disclosed with its reason."""
    source_bytes = source.encode("utf-8")
    reachable = []
    deferred = []
    unreachable = []
    for if_node in _fault_ifs(source_bytes):
        code = _fault_code(if_node.child_by_field_name("consequence"), source_bytes)
        condition = if_node.child_by_field_name("condition")
        if _has_call(condition):
            unreachable.append({"code": code, "reason": "state-dependent"})
            continue
        trigger = _solved_trigger(condition, source_bytes)
        if trigger is None:
            deferred.append({"code": code, "reason": "needs-perturbation"})
            continue
        reachable.append({"code": code, "trigger": trigger})
    return {"reachable": reachable, "deferred": deferred, "unreachable": unreachable}
