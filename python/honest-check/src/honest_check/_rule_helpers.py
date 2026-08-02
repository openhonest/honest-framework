"""Shared helpers and constants for the honest-check rule families.

Pure AST helpers and closed-set constants used across the HC-P Honest-Code rules,
the honest-type vocabulary/chain/state rules, and the integration rules. This module
imports only from honest_parse / honest_check.declgraph / honest_check.diagnostics —
never from a rule module or rules.py — so the rule modules can depend on it freely.
"""

from honest_check.declgraph import (
    module_assignments,
    string_value,
)
from honest_check.diagnostics import (
    Diagnostic,
    diagnostic,
)
from honest_parse import (
    line_col,
    node_text,
    walk,
)


# Section 4.2 / 5.3 — the only class bases Honest Code permits.
_ALLOWED_CLASS_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)


# Minimum branch count for HC-P001 to consider an if-chain a dispatch (section 4.2).
_DISPATCH_BRANCH_THRESHOLD = 3


def _simple_base_name(text: str) -> str:
    """Reduce a base expression to its bare name: 'typing.Protocol' -> 'Protocol'."""
    return text.split("[")[0].split(".")[-1].strip()


def _class_base_names(class_node, source: bytes) -> list[str]:
    """Names of a class's explicit bases, ignoring keyword args like total=False."""
    supers = class_node.child_by_field_name("superclasses")
    if supers is None:
        return []
    names = []
    for child in supers.named_children:
        if child.type == "subscript":
            value = child.child_by_field_name("value")
            names.append(node_text(value, source) if value is not None else "")
        if child.type in ("identifier", "attribute"):
            names.append(node_text(child, source))
    return names


def _typeddict_names(root, source: bytes) -> set:
    """The names of TypedDict classes declared in this file (section 4.2). An instance of one of these
    is a dict, so returning it is serializable and fine; any other class instance is not."""
    names: set = set()
    for node in walk(root):
        if node.type != "class_definition":
            continue
        if any(_simple_base_name(base) == "TypedDict" for base in _class_base_names(node, source)):
            names.add(node_text(node.child_by_field_name("name"), source))
    return names


# Immutable read-only mappings are honest data, not opaque objects: serializable via dict() and
# preferable to a mutable dict for a shared constant (section 4.2). Accepted like dict/TypedDict.
_IMMUTABLE_MAPPINGS = frozenset({"MappingProxyType"})


def _equality_target(condition, source: bytes) -> str | None:
    """If `condition` is `IDENT == value`, return IDENT's text; else None."""
    if condition.type != "comparison_operator":
        return None
    if not any(child.type == "==" for child in condition.children):
        return None
    operands = condition.named_children
    left = operands[0]
    if left.type != "identifier":
        return None
    return node_text(left, source)


def _if_chain_conditions(if_node):
    """Every condition guarding a branch of an if-statement: the if plus each elif."""
    conditions = [if_node.child_by_field_name("condition")]
    for child in if_node.children:
        if child.type == "elif_clause":
            conditions.append(child.child_by_field_name("condition"))
    return [c for c in conditions if c is not None]


# Section 4.2 / 5.7 — framework lifecycle hooks. Their presence means behaviour is
# wired to a hidden lifecycle instead of to server-rendered HTML / HTMX attributes.
_LIFECYCLE_HOOKS = frozenset(
    {
        "useEffect",
        "useLayoutEffect",
        "componentDidMount",
        "componentDidUpdate",
        "componentWillUnmount",
        "ngOnInit",
        "ngOnDestroy",
        "addEventListener",
        "removeEventListener",
    }
)


def _call_name(call_node, source: bytes) -> str:
    """The callee name of a call: 'foo' for foo(), 'bar' for obj.bar()."""
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return ""
    if fn.type == "attribute":
        attr = fn.child_by_field_name("attribute")
        return node_text(attr, source) if attr is not None else ""
    return node_text(fn, source)


_UNBOUNDED_CALL_BUILTINS = frozenset({"eval", "exec"})
_DYNAMIC_IMPORT_CALLS = frozenset({"import_module", "__import__"})


def _string_positional(call_node, index: int) -> bool:
    """Whether the call's nth positional argument is a string literal — a bounded, fixed target. Called
    only with call nodes, whose `arguments` field is always present."""
    positional = [child for child in call_node.child_by_field_name("arguments").named_children if child.type != "keyword_argument"]
    return index < len(positional) and positional[index].type == "string"


def _class_methods(class_node):
    """The function_definition nodes directly in a class body."""
    body = class_node.child_by_field_name("body")
    if body is None:
        return []
    return [child for child in body.children if child.type == "function_definition"]


def _self_attr_writes(func_node, source: bytes) -> list[str]:
    """Attribute names assigned on `self` anywhere in a method body."""
    writes: list[str] = []
    for node in walk(func_node):
        if node.type not in ("assignment", "augmented_assignment"):
            continue
        left = node.child_by_field_name("left")
        for sub in walk(left):
            if sub.type != "attribute":
                continue
            obj = sub.child_by_field_name("object")
            attr = sub.child_by_field_name("attribute")
            if node_text(obj, source) == "self":
                writes.append(node_text(attr, source))
    return writes


def _direct_nonlocal_names(func_node, source: bytes) -> set[str]:
    """Names declared `nonlocal` at the top level of a function body."""
    names: set[str] = set()
    body = func_node.child_by_field_name("body")
    if body is None:
        return names
    for child in body.children:
        if child.type != "nonlocal_statement":
            continue
        for ident in child.named_children:
            names.add(node_text(ident, source))
    return names


def _rebinds_name(func_node, name: str, source: bytes) -> bool:
    """True if `name` is the direct target of an assignment in the function."""
    for node in walk(func_node):
        if node.type not in ("assignment", "augmented_assignment"):
            continue
        left = node.child_by_field_name("left")
        if left.type == "identifier" and node_text(left, source) == name:
            return True
        if left.type in ("pattern_list", "tuple_pattern", "tuple"):
            for sub in left.named_children:
                if sub.type == "identifier" and node_text(sub, source) == name:
                    return True
    return False


def _dotted_name(node, source: bytes) -> str:
    """The dotted path of a name/attribute expression: 'os.path.join', 'print', or ''."""
    if node.type == "identifier":
        return node_text(node, source)
    if node.type == "attribute":
        obj = node.child_by_field_name("object")
        attr = node.child_by_field_name("attribute")
        name = node_text(attr, source) if attr is not None else ""
        prefix = _dotted_name(obj, source) if obj is not None else ""
        return f"{prefix}.{name}" if prefix else name
    return ""


def _qualified_call_name(call_node, source: bytes) -> str:
    """The dotted callee of a call expression, or '' if the callee is not a name path."""
    fn = call_node.child_by_field_name("function")
    return _dotted_name(fn, source) if fn is not None else ""


def _decorators(func_node):
    """Decorator nodes attached to a function (via its decorated_definition parent)."""
    parent = func_node.parent
    if parent is None or parent.type != "decorated_definition":
        return []
    return [child for child in parent.children if child.type == "decorator"]


def _is_boundary_function(func_node, source: bytes) -> bool:
    """A function is a boundary if decorated @boundary or @link(..., boundary=True)."""
    for decorator in _decorators(func_node):
        compact = node_text(decorator, source).replace(" ", "")
        if compact == "@boundary" or compact.startswith("@boundary("):
            return True
        if "boundary=True" in compact:
            return True
    return False


def _enclosing_function(node):
    """The nearest enclosing function_definition, or None if at module level."""
    current = node.parent
    while current is not None:
        if current.type == "function_definition":
            return current
        current = current.parent
    return None


# Methods that mutate a container in place, and the container-literal node types.
_MUTATING_METHODS = frozenset(
    {
        "append", "add", "update", "pop", "popitem", "clear", "insert",
        "remove", "extend", "setdefault", "discard", "sort", "reverse",
    }
)
_CONTAINER_LITERALS = frozenset(
    {"dictionary", "list", "set", "list_comprehension", "set_comprehension", "dictionary_comprehension"}
)


def _subscript_base(node, source: bytes):
    """For a subscript target `X[...]`, the base name X (if X is a plain name)."""
    if node.type != "subscript":
        return None
    value = node.child_by_field_name("value")
    if value is not None and value.type == "identifier":
        return node_text(value, source)
    return None


def _mutable_module_containers(root, source: bytes) -> set[str]:
    """Module-level dict/list/set names that are *mutated* — genuine hidden state.

    A module-level container that is never mutated is a constant lookup table — the
    dict-lookup-polymorphism pattern the framework mandates (honest-code-principles)
    — and is exempt. Only containers written to (subscript-assign, mutating method,
    del, or reassignment) carry state across calls and are flagged.
    """
    candidates: set[str] = set()
    assign_count: dict[str, int] = {}
    for assignment in module_assignments(root):
        left = assignment.child_by_field_name("left")
        right = assignment.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        name = node_text(left, source)
        assign_count[name] = assign_count.get(name, 0) + 1
        if right.type in _CONTAINER_LITERALS:
            candidates.add(name)

    mutated: set[str] = set()
    for node in walk(root):
        if node.type in ("assignment", "augmented_assignment"):
            left = node.child_by_field_name("left")
            base = _subscript_base(left, source) if left is not None else None
            if base is not None:
                mutated.add(base)
        if node.type == "delete_statement":
            for target in node.named_children:
                base = _subscript_base(target, source)
                if base is not None:
                    mutated.add(base)
        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn is not None and fn.type == "attribute":
                obj = fn.child_by_field_name("object")
                attr = fn.child_by_field_name("attribute")
                if (
                    obj is not None
                    and obj.type == "identifier"
                    and attr is not None
                    and node_text(attr, source) in _MUTATING_METHODS
                ):
                    mutated.add(node_text(obj, source))
    for name, count in assign_count.items():
        if count > 1:
            mutated.add(name)
    return candidates & mutated


def _local_names(func_node, source: bytes) -> set[str]:
    """Names bound locally in a function: parameters, assignment and for targets."""
    names: set[str] = set()
    params = func_node.child_by_field_name("parameters")
    if params is not None:
        for param in params.named_children:
            for sub in walk(param):
                if sub.type == "identifier":
                    names.add(node_text(sub, source))
                    break
    body = func_node.child_by_field_name("body")
    if body is not None:
        for node in walk(body):
            if node.type in ("assignment", "augmented_assignment"):
                left = node.child_by_field_name("left")
                if left is not None and left.type == "identifier":
                    names.add(node_text(left, source))
            if node.type == "for_statement":
                left = node.child_by_field_name("left")
                for sub in walk(left):
                    if sub.type == "identifier":
                        names.add(node_text(sub, source))
    return names


def _is_value_load(node) -> bool:
    """True if an identifier is read as a value, not used as a name label."""
    parent = node.parent
    if parent is None:
        return True
    if parent.type == "attribute" and parent.child_by_field_name("attribute") == node:
        return False
    if parent.type == "keyword_argument" and parent.child_by_field_name("name") == node:
        return False
    return True


def _check_global_reads(root, source: bytes, path: str, mutable: set[str]) -> list[Diagnostic]:
    """Reads of module-level mutable state inside non-boundary functions (HC-P004)."""
    out: list[Diagnostic] = []
    for func in walk(root):
        if func.type != "function_definition" or _is_boundary_function(func, source):
            continue
        body = func.child_by_field_name("body")
        local = _local_names(func, source)
        seen: set[str] = set()
        for node in walk(body):
            if node.type != "identifier":
                continue
            name = node_text(node, source)
            if name not in mutable or name in local or name in seen or not _is_value_load(node):
                continue
            seen.add(name)
            line, col = line_col(node)
            out.append(
                diagnostic(
                    "HC-P004",
                    "error",
                    path,
                    line,
                    col,
                    f"Reads module-level mutable state '{name}' inside a non-boundary "
                    "function. Module-level mutable state is hidden state — pass it as a "
                    "parameter or move it into persist.",
                )
            )
    return out


# Section 4.2 / 5.6 — cache decorators. A cache is a performance claim and must be
# backed by profiling evidence, else it is unjustified hidden state.
_CACHE_DECORATORS = frozenset({"lru_cache", "cache", "memoize", "cached_property"})


def _decorator_name(decorator, source: bytes) -> str:
    """Bare name of a decorator: '@functools.lru_cache(maxsize=8)' -> 'lru_cache'."""
    body = node_text(decorator, source).lstrip("@").strip()
    return body.split("(")[0].split(".")[-1].strip()


def _is_profiled_comment(node, source: bytes) -> bool:
    text = node_text(node, source)
    return node.type == "comment" and "honest:" in text and "profiled" in text


def _has_profiling_evidence(func_node, source: bytes) -> bool:
    """True if the function carries @profiled or a '# honest: profiled' comment."""
    for decorator in _decorators(func_node):
        if _decorator_name(decorator, source) == "profiled":
            return True
    parent = func_node.parent
    anchor = parent if parent is not None and parent.type == "decorated_definition" else func_node
    # Comments between decorators (inside the definition).
    for node in walk(anchor):
        if _is_profiled_comment(node, source):
            return True
    # Comments on the lines immediately preceding the (decorated) definition.
    sibling = anchor.prev_sibling
    while sibling is not None and sibling.type == "comment":
        if _is_profiled_comment(sibling, source):
            return True
        sibling = sibling.prev_sibling
    return False


def _reachable_states(initial: str, transitions) -> set[str]:
    """States reachable from `initial` by following transitions (BFS)."""
    reachable = {initial}
    frontier = [initial]
    while frontier:
        nxt: list[str] = []
        for state in frontier:
            for source_state, _event, target in transitions:
                if source_state == state and target is not None and target not in reachable:
                    reachable.add(target)
                    nxt.append(target)
        frontier = nxt
    return reachable


def _has_except_clause(try_node) -> bool:
    """True if a try statement catches (has an except clause), vs try/finally cleanup."""
    return any(
        child.type in ("except_clause", "except_group_clause") for child in try_node.children
    )


def _produced_slot_keys(func_node, source: bytes) -> set[str]:
    """Manifest slot keys a link body writes: subscript-assign targets and dict-literal keys."""
    keys: set[str] = set()
    body = func_node.child_by_field_name("body")
    if body is None:
        return keys
    for node in walk(body):
        if node.type in ("assignment", "augmented_assignment"):
            left = node.child_by_field_name("left")
            if left is not None and left.type == "subscript":
                for child in left.named_children:
                    if child.type == "string":
                        value = string_value(child, source)
                        keys.add(value)
        if node.type == "dictionary":
            for pair in node.named_children:
                if pair.type != "pair":
                    continue
                key = pair.child_by_field_name("key")
                value = string_value(key, source) if key is not None else None
                if value is not None:
                    keys.add(value)
    return keys


def _recognizer_identity(recognizer):
    """A hashable identity for a recognizer, or None if it cannot be compared statically."""
    kind = recognizer[0]
    if kind == "set":
        return ("set", recognizer[1])
    if kind == "ref":
        return ("ref", recognizer[1])
    return None  # predicates are opaque — treat each as unique, no reuse detection


# Manifest keys that route to a database and so must be bounded Set recognizers, never predicates
# (honest-persist section 8.4 — the vocabulary is the whitelist).
_ROUTING_KEYS = frozenset({"db_id", "tenant_id", "credential"})


# Minimum shared consecutive-call run before HC-OR003 fires (section 4.2, default 3).
_OR003_MIN_RUN = 3


def _orchestrator_call_sequence(func_node, source: bytes) -> list[str]:
    """The orchestrator body normalized to its ordered sequence of qualified call names."""
    body = func_node.child_by_field_name("body")
    if body is None:
        return []
    return [
        _qualified_call_name(node, source)
        for node in walk(body)
        if node.type == "call" and _qualified_call_name(node, source)
    ]


def _longest_common_run(first: list[str], second: list[str]) -> int:
    """Length of the longest common *contiguous* sublist of two sequences."""
    if not first or not second:
        return 0
    best = 0
    previous = [0] * (len(second) + 1)
    for i in range(1, len(first) + 1):
        current = [0] * (len(second) + 1)
        for j in range(1, len(second) + 1):
            if first[i - 1] == second[j - 1]:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best


_HTTP_RESPONSE_MARKERS = frozenset(
    {
        "Response", "JSONResponse", "HTMLResponse", "PlainTextResponse",
        "RedirectResponse", "StreamingResponse", "FileResponse",
    }
)


# Calls that throw on input outside their expected shape (section 4.2, HC009).
_RISKY_PREDICATE_CALLS = frozenset({"int", "float"})


def _risky_predicate_ops(value_node, source: bytes) -> set[str]:
    """Operations in a predicate body that can raise on non-matching input."""
    risky: set[str] = set()
    for node in walk(value_node):
        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn is not None and fn.type == "identifier" and node_text(fn, source) in _RISKY_PREDICATE_CALLS:
                risky.add(node_text(fn, source) + "()")
        if node.type == "subscript":
            risky.add("index")
        if node.type == "binary_operator":
            for child in node.children:
                if child.type in ("/", "//"):
                    risky.add("division")
    return risky
