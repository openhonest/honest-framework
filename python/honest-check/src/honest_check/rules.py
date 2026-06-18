"""Rule registry and the check_source entry point (sections 4, 8).

Each rule is a pure function `check(root_node, source_bytes, path) -> list[Diagnostic]`.
Rules are registered in `_ALL_CHECKS`; `check_source` parses once, short-circuits on
a syntax error (HC-SYN), then runs every registered rule. New rules are added by
writing the function and appending it to the registry — a row, not a branch.

This unit implements the two structural rules that make class-based smuggling and
value-dispatch chains impossible to represent: HC-P003 (class declaration) and
HC-P001 (if/elif/else dispatch). Both cite honest-check-architecture.md section 4.2.
"""

from itertools import combinations

from honest_check.declgraph import (
    assigned_name,
    build_vocabulary_definitions,
    call_location,
    constructor_calls,
    defined_function_names,
    extract_chains,
    extract_links,
    extract_state_machines,
    module_assignments,
    positional_arg_count,
    resolve_aliases,
    vocabulary_base_types,
)
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import first_error_node, line_col, node_text, parse_python, walk
from honest_check.suppression import build_suppressions, is_suppressed
from honest_check.watchlists import (
    IO_WATCH_LIST,
    NONDETERMINISTIC_WATCH_LIST,
    matches_watchlist,
)

# Section 4.2 / 5.3 — the only class bases Honest Code permits.
_ALLOWED_CLASS_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)

# Minimum branch count for HC-P001 to consider an if-chain a dispatch (section 4.2).
_DISPATCH_BRANCH_THRESHOLD = 3


def check_hc_syn(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SYN — source does not parse. Short-circuits all other rules."""
    if not root.has_error:
        return []
    node = first_error_node(root)
    line, col = line_col(node) if node is not None else (1, 1)
    return [
        diagnostic("HC-SYN", "error", path, line, col, "Source does not parse.")
    ]


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


def check_hc_p003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P003 — class declaration (bare class, or inheritance from a non-approved base)."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "class_definition":
            continue
        name_node = node.child_by_field_name("name")
        name = node_text(name_node, source) if name_node is not None else "<anonymous>"
        line, col = line_col(node)
        bases = _class_base_names(node, source)
        if not bases:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' has no declared base. Honest Code permits class "
                    "definitions only as subclasses of TypedDict, Protocol, ABC, or a "
                    "declared Exception. Use a TypedDict for data shapes or a pure function.",
                )
            )
            continue
        for base in bases:
            if _simple_base_name(base) not in _ALLOWED_CLASS_BASES:
                out.append(
                    diagnostic(
                        "HC-P003",
                        "error",
                        path,
                        line,
                        col,
                        f"Class '{name}' inherits from '{base}'. "
                        "Use composition over inheritance.",
                    )
                )
    return out


def _equality_target(condition, source: bytes) -> str | None:
    """If `condition` is `IDENT == value`, return IDENT's text; else None."""
    if condition.type != "comparison_operator":
        return None
    if not any(child.type == "==" for child in condition.children):
        return None
    operands = condition.named_children
    if len(operands) < 2:
        return None
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


def check_hc_p001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P001 — if/elif/else chain dispatching on a single value. Use a dict table."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "if_statement":
            continue
        targets = [
            t
            for t in (_equality_target(c, source) for c in _if_chain_conditions(node))
            if t is not None
        ]
        if len(targets) < _DISPATCH_BRANCH_THRESHOLD:
            continue
        if len(set(targets)) != 1:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P001",
                "error",
                path,
                line,
                col,
                "if/elif/else chain dispatches on value — use dict lookup. "
                "See honest-code-principles.md §3.",
            )
        )
    return out


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


def check_hc_p011(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P011 — framework lifecycle hook. Use HTMX attributes / server-rendered HTML."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call":
            continue
        name = _call_name(node, source)
        if name not in _LIFECYCLE_HOOKS:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P011",
                "error",
                path,
                line,
                col,
                f"Lifecycle hook '{name}'. Use HTMX attributes or server-rendered HTML.",
            )
        )
    return out


def _class_methods(class_node):
    """The function_definition nodes directly in a class body."""
    body = class_node.child_by_field_name("body")
    if body is None:
        return []
    return [child for child in body.children if child.type == "function_definition"]


def _function_name(func_node, source: bytes) -> str:
    name_node = func_node.child_by_field_name("name")
    return node_text(name_node, source) if name_node is not None else "<anonymous>"


def _self_attr_writes(func_node, source: bytes) -> list[str]:
    """Attribute names assigned on `self` anywhere in a method body."""
    writes: list[str] = []
    for node in walk(func_node):
        if node.type not in ("assignment", "augmented_assignment"):
            continue
        left = node.child_by_field_name("left")
        if left is None:
            continue
        for sub in walk(left):
            if sub.type != "attribute":
                continue
            obj = sub.child_by_field_name("object")
            attr = sub.child_by_field_name("attribute")
            if obj is None or attr is None:
                continue
            if node_text(obj, source) == "self":
                writes.append(node_text(attr, source))
    return writes


def check_hc_p002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P002 — class method mutates self. __init__ is a warning; others are errors."""
    out: list[Diagnostic] = []
    for cls in walk(root):
        if cls.type != "class_definition":
            continue
        for method in _class_methods(cls):
            if not _self_attr_writes(method, source):
                continue
            name = _function_name(method, source)
            severity = "warning" if name == "__init__" else "error"
            line, col = line_col(method)
            out.append(
                diagnostic(
                    "HC-P002",
                    severity,
                    path,
                    line,
                    col,
                    f"Method '{name}' mutates self. Use TypedDict + pure function.",
                )
            )
    return out


def check_hc_p007(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P007 — underscore-prefixed instance state set in a constructor (warning)."""
    out: list[Diagnostic] = []
    for cls in walk(root):
        if cls.type != "class_definition":
            continue
        for method in _class_methods(cls):
            if _function_name(method, source) != "__init__":
                continue
            for attr in _self_attr_writes(method, source):
                if not attr.startswith("_"):
                    continue
                line, col = line_col(method)
                out.append(
                    diagnostic(
                        "HC-P007",
                        "warning",
                        path,
                        line,
                        col,
                        f"Instance state '{attr}'. Pass as parameter or use context manager.",
                    )
                )
    return out


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
        if left is None:
            continue
        if left.type == "identifier" and node_text(left, source) == name:
            return True
        if left.type in ("pattern_list", "tuple_pattern", "tuple"):
            for sub in left.named_children:
                if sub.type == "identifier" and node_text(sub, source) == name:
                    return True
    return False


def check_hc_p016(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P016 — inner function captures an enclosing name via nonlocal and mutates it."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        captured = _direct_nonlocal_names(node, source)
        if not captured:
            continue
        mutated = sorted(n for n in captured if _rebinds_name(node, n, source))
        if not mutated:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P016",
                "error",
                path,
                line,
                col,
                f"Inner function '{_function_name(node, source)}' captures {mutated} via "
                "nonlocal and mutates it. Closures may not carry mutable state — use pure "
                "parameters or move state into persist.",
            )
        )
    return out


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
                if left is not None:
                    for sub in walk(left):
                        if sub.type == "identifier":
                            names.add(node_text(sub, source))
    return names


def _is_value_load(node) -> bool:
    """True if an identifier is read as a value, not used as a name label."""
    parent = node.parent
    if parent is None:
        return True
    if parent.type == "attribute" and parent.child_by_field_name("attribute") is node:
        return False
    if parent.type == "keyword_argument" and parent.child_by_field_name("name") is node:
        return False
    return True


def _check_global_reads(root, source: bytes, path: str, mutable: set[str]) -> list[Diagnostic]:
    """Reads of module-level mutable state inside non-boundary functions (HC-P004)."""
    out: list[Diagnostic] = []
    for func in walk(root):
        if func.type != "function_definition" or _is_boundary_function(func, source):
            continue
        body = func.child_by_field_name("body")
        if body is None:
            continue
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


def check_hc_p004(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P004 — I/O, non-determinism, or hidden module state in a non-boundary function."""
    io = IO_WATCH_LIST["python"]
    nondeterministic = NONDETERMINISTIC_WATCH_LIST["python"]
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call":
            continue
        name = _qualified_call_name(node, source)
        if not (matches_watchlist(name, io) or matches_watchlist(name, nondeterministic)):
            continue
        enclosing = _enclosing_function(node)
        if enclosing is None or _is_boundary_function(enclosing, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P004",
                "error",
                path,
                line,
                col,
                f"Call '{name}' performs I/O or non-deterministic work inside a "
                "non-boundary function. Move it to a boundary (decorate @boundary or "
                "@link(boundary=True)), or it cannot be verified for purity.",
            )
        )
    out.extend(_check_global_reads(root, source, path, _mutable_module_containers(root, source)))
    return out


def check_hc_p005(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P005 — isinstance()/type() used outside a boundary function (warning)."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call":
            continue
        name = _qualified_call_name(node, source)
        if name not in ("isinstance", "type"):
            continue
        enclosing = _enclosing_function(node)
        if enclosing is not None and _is_boundary_function(enclosing, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P005",
                "warning",
                path,
                line,
                col,
                f"{name}() check in business logic. Consider a vocabulary declaration instead.",
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


def check_hc_p006(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P006 — cache decorator without profiling annotation (warning)."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        cache_decorators = [
            d for d in _decorators(node) if _decorator_name(d, source) in _CACHE_DECORATORS
        ]
        if not cache_decorators or _has_profiling_evidence(node, source):
            continue
        line, col = line_col(cache_decorators[0])
        out.append(
            diagnostic(
                "HC-P006",
                "warning",
                path,
                line,
                col,
                "Cache detected without profiling evidence. Add a @profiled annotation "
                "or a '# honest: profiled' comment.",
            )
        )
    return out


def check_hc007(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC007 — a chain() with no links cannot be tested (error, section 4.1)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "chain"):
        if positional_arg_count(call) != 0:
            continue
        line, col = call_location(call)
        name = assigned_name(call, source) or "<anonymous>"
        out.append(diagnostic("HC007", "error", path, line, col, f"Chain '{name}' has no links."))
    return out


def check_hc003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC003 — two types in one vocabulary match the same token (section 4.1).

    Set x Set overlap is decidable here (error). Predicate x Predicate cannot be
    decided statically, so an info points to honest-test. Set x Predicate (needs
    evaluating the predicate over the Set) is deferred to honest-test.
    """
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        line, col = call_location(call)
        for (name_a, rec_a), (name_b, rec_b) in combinations(
            sorted(vocabulary_base_types(call, source).items()), 2
        ):
            if rec_a[0] == "set" and rec_b[0] == "set":
                overlap = rec_a[1] & rec_b[1]
                if overlap:
                    out.append(
                        diagnostic(
                            "HC003",
                            "error",
                            path,
                            line,
                            col,
                            f"Types '{name_a}' and '{name_b}' share values: {sorted(overlap)}.",
                        )
                    )
            if rec_a[0] == "predicate" and rec_b[0] == "predicate":
                out.append(
                    diagnostic(
                        "HC003",
                        "info",
                        path,
                        line,
                        col,
                        f"Predicate types '{name_a}' and '{name_b}' may overlap — "
                        "cannot be checked statically; verified by honest-test.",
                    )
                )
    return out


def check_state_machine_vocab(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SM01/02/05 — transition or initial state/event not in its vocabulary (section 4.1)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for machine in extract_state_machines(root, source, aliases):
        line, col = machine["location"]
        if machine["states"]:
            for state, _event, _next in machine["transitions"]:
                if state not in machine["states"]:
                    out.append(diagnostic("HC-SM01", "error", path, line, col,
                        f"State '{state}' in transition table not in states vocabulary."))
            initial = machine["initial"]
            if initial is not None and initial not in machine["states"]:
                out.append(diagnostic("HC-SM05", "error", path, line, col,
                    f"Initial state '{initial}' not in states vocabulary."))
        if machine["events"]:
            for _state, event, _next in machine["transitions"]:
                if event not in machine["events"]:
                    out.append(diagnostic("HC-SM02", "error", path, line, col,
                        f"Event '{event}' in transition table not in events vocabulary."))
    return out


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


def check_state_machine_reachability(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SM03/04 — unreachable states and dead non-terminal states (section 4.2)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for machine in extract_state_machines(root, source, aliases):
        if not machine["states"] or machine["initial"] is None:
            continue
        line, col = machine["location"]
        transitions = machine["transitions"]
        reachable = _reachable_states(machine["initial"], transitions)
        for state in sorted(machine["states"]):
            if state not in reachable and state != machine["initial"]:
                out.append(diagnostic("HC-SM03", "warning", path, line, col,
                    f"State '{state}' is unreachable."))
        for state in sorted(machine["states"]):
            has_outgoing = any(src == state for src, _event, _target in transitions)
            if not has_outgoing and state not in machine["terminal"]:
                out.append(diagnostic("HC-SM04", "warning", path, line, col,
                    f"State '{state}' has no outgoing transitions and is not declared terminal."))
    return out


def check_hc001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC001 — a function used in a chain has no @link vocabulary declared (error)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    links = extract_links(root, source, aliases, vocab_defs)
    defined = defined_function_names(root, source)
    out: list[Diagnostic] = []
    for chain in extract_chains(root, source, aliases):
        line, col = chain["location"]
        for link_name in chain["links"]:
            if link_name in links or link_name not in defined:
                # A link, or an external/chain reference we cannot judge — skip.
                continue
            out.append(
                diagnostic(
                    "HC001",
                    "error",
                    path,
                    line,
                    col,
                    f"Function '{link_name}' in chain has no vocabulary declared. "
                    "Wrap with @link(accepts=..., emits=...).",
                )
            )
    return out


def check_hc002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC002 — a link accepts types its predecessor does not emit (error)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    links = extract_links(root, source, aliases, vocab_defs)
    out: list[Diagnostic] = []
    for chain in extract_chains(root, source, aliases):
        line, col = chain["location"]
        sequence = chain["links"]
        for index in range(1, len(sequence)):
            previous = links.get(sequence[index - 1])
            current = links.get(sequence[index])
            if previous is None or current is None:
                continue
            emits = previous["emits"]
            accepts = current["accepts"]
            if not emits or not accepts:
                continue
            missing = accepts - emits
            if missing:
                out.append(
                    diagnostic(
                        "HC002",
                        "error",
                        path,
                        line,
                        col,
                        f"Link '{sequence[index]}' accepts types not provided by previous "
                        f"link '{sequence[index - 1]}': {sorted(missing)}.",
                    )
                )
    return out


# Registry. Order is report order; each entry is one rule function (section 8).
_ALL_CHECKS = (
    check_hc001,
    check_hc002,
    check_hc003,
    check_hc007,
    check_state_machine_vocab,
    check_state_machine_reachability,
    check_hc_p001,
    check_hc_p002,
    check_hc_p003,
    check_hc_p004,
    check_hc_p005,
    check_hc_p006,
    check_hc_p007,
    check_hc_p011,
    check_hc_p016,
)


def check_source(source: str, path: str) -> list[Diagnostic]:
    """Parse `source`, run every registered rule, then apply suppressions (section 1, 7)."""
    src_bytes = source.encode("utf-8")
    root = parse_python(src_bytes).root_node
    syntax = check_hc_syn(root, src_bytes, path)
    if syntax:
        return syntax

    raw: list[Diagnostic] = []
    for check in _ALL_CHECKS:
        raw.extend(check(root, src_bytes, path))

    max_line = root.end_point[0] + 1
    inline, ranges = build_suppressions(root, src_bytes, max_line)
    out: list[Diagnostic] = []
    for d in raw:
        if is_suppressed(d["rule"], d["line"], inline, ranges):
            out.append(
                diagnostic(
                    d["rule"],
                    "info",
                    d["path"],
                    d["line"],
                    d["col"],
                    f"{d['rule']} suppressed by directive.",
                )
            )
        else:
            out.append(d)
    return out
