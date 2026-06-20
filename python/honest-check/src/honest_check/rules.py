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
    authorizing_links,
    build_vocabulary_definitions,
    call_location,
    constructor_calls,
    defined_function_names,
    extract_bindings,
    extract_chains,
    extract_composed_types,
    extract_links,
    extract_state_machines,
    extract_vocabularies,
    function_calls,
    function_name,
    function_role,
    functions_by_name,
    keyword_args,
    link_decorator_call,
    module_assignments,
    positional_arg_count,
    registered_provider_signature,
    resolve_aliases,
    string_value,
    vocab_binding_pairings,
    vocab_expr_type_names,
    vocabulary_base_types,
)
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_parse import first_error_node, line_col, node_text, parse_python, walk
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


def check_hc_p007(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P007 — underscore-prefixed instance state set in a constructor (warning)."""
    out: list[Diagnostic] = []
    for cls in walk(root):
        if cls.type != "class_definition":
            continue
        for method in _class_methods(cls):
            if function_name(method, source) != "__init__":
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
                f"Inner function '{function_name(node, source)}' captures {mutated} via "
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


def check_hc_r001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-R001 — orphan function: no declared role and not reachable from a roled one.

    Gated to files that declare at least one role, so plain non-framework modules are
    not swept. Auto-generation reaches roled functions and, transitively, the helpers
    they call; anything left over has no test story.
    """
    aliases = resolve_aliases(root, source)
    functions = functions_by_name(root, source)
    roled = {name for name, node in functions.items() if function_role(node, source) is not None}
    if not roled:
        return []
    calls = {name: function_calls(node, source) for name, node in functions.items()}
    reachable = set(roled)
    frontier = list(roled)
    while frontier:
        nxt: list[str] = []
        for caller in frontier:
            for callee in calls.get(caller, set()):
                if callee in functions and callee not in reachable:
                    reachable.add(callee)
                    nxt.append(callee)
        frontier = nxt
    out: list[Diagnostic] = []
    for name, node in functions.items():
        if name in reachable:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-R001",
                "error",
                path,
                line,
                col,
                f"Function '{name}' has no declared role and is not called by any roled "
                "function. Declare a role (@link / @recognizer / @boundary / @helper) or remove it.",
            )
        )
    return out


def check_hc_or001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-OR001 — an orchestrator calls another orchestrator (error). They do not compose."""
    functions = functions_by_name(root, source)
    orchestrators = {
        name for name, node in functions.items() if function_role(node, source) == "orchestrator"
    }
    out: list[Diagnostic] = []
    for name in sorted(orchestrators):
        for callee in sorted(function_calls(functions[name], source)):
            if callee in orchestrators:
                line, col = line_col(functions[name])
                out.append(
                    diagnostic(
                        "HC-OR001",
                        "error",
                        path,
                        line,
                        col,
                        f"Orchestrator '{name}' calls orchestrator '{callee}'. Orchestrators "
                        "do not compose — extract shared logic as a pure helper or a chain.",
                    )
                )
    return out


def _has_except_clause(try_node) -> bool:
    """True if a try statement catches (has an except clause), vs try/finally cleanup."""
    return any(
        child.type in ("except_clause", "except_group_clause") for child in try_node.children
    )


def check_hc_p002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P002 — an exception is caught inside a non-boundary function (error).

    Honest Code principle 'Typed Exceptions at the Boundary': business logic raises;
    boundaries catch. A try/except in a non-boundary function swallows faults and hides
    the caught path from the manifest. try/finally without except (cleanup) is allowed.
    (Formerly 'class with mutating methods' — redundant under NO CLASSES / HC-P003.)
    """
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "try_statement" or not _has_except_clause(node):
            continue
        enclosing = _enclosing_function(node)
        if enclosing is None or _is_boundary_function(enclosing, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P002",
                "error",
                path,
                line,
                col,
                f"Function '{function_name(enclosing, source)}' catches an exception in "
                "business logic. Let it raise and catch at the boundary (@boundary / route "
                "handler), or return a fault as data.",
            )
        )
    return out


# The canonical persist read API (honest-persist §7.4/§7.5). A guard slot whose value
# traces to one of these is stale at commit — the cross-chain TOCTOU HC-P015 rejects.
_PERSIST_READ_CALLS = frozenset({"persist.read", "persist.execute", "persist.query"})


def _is_persist_read(call_node, source: bytes) -> bool:
    return _qualified_call_name(call_node, source) in _PERSIST_READ_CALLS


def _subscript_string_key(subscript_node, source: bytes):
    """The string key of a `manifest['slot']` subscript target, or None."""
    for child in subscript_node.named_children:
        if child.type == "string":
            return string_value(child, source)
    return None


def _guard_slot_names(guard_node, source: bytes) -> set[str]:
    """Every slot('name') term reachable in a guard expression tree (honest-persist §7.5)."""
    names: set[str] = set()
    for node in walk(guard_node):
        if node.type != "call" or _call_name(node, source) != "slot":
            continue
        args = node.child_by_field_name("arguments")
        for arg in args.named_children:
            if arg.type == "string":
                value = string_value(arg, source)
                names.add(value)
                break
    return names


def _persist_tainted_slots(func_node, source: bytes) -> set[str]:
    """Manifest slots written from a persist read (directly or one hop via a local var)."""
    body = func_node.child_by_field_name("body")
    if body is None:
        return set()
    tainted_vars: set[str] = set()
    for node in walk(body):
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        if right.type == "call" and _is_persist_read(right, source):
            tainted_vars.add(node_text(left, source))
    tainted_slots: set[str] = set()
    for node in walk(body):
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "subscript":
            continue
        key = _subscript_string_key(left, source)
        if key is None:
            continue
        if right.type == "call" and _is_persist_read(right, source):
            tainted_slots.add(key)
        elif right.type == "identifier" and node_text(right, source) in tainted_vars:
            tainted_slots.add(key)
    return tainted_slots


def check_hc_p015(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P015 — a guard references a slot whose value came from a prior persist read (error)."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call" or _call_name(node, source) != "guarded_mutation":
            continue
        guard = keyword_args(node, source).get("guard")
        if guard is None:
            continue
        guard_slots = _guard_slot_names(guard, source)
        if not guard_slots:
            continue
        enclosing = _enclosing_function(node)
        if enclosing is None:
            continue
        stale = sorted(guard_slots & _persist_tainted_slots(enclosing, source))
        if not stale:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P015",
                "error",
                path,
                line,
                col,
                f"Guard references slot(s) {stale} whose value comes from a prior persist "
                "read in the chain — a cross-chain TOCTOU; the read may be stale at commit. "
                "Move the check into the guard via a persist-side lookup (lookup/derive/"
                "count), or fuse the read and the write into one guarded_mutation.",
            )
        )
    return out


def check_hc_a001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-A001 — links declare authorizes=True but no AuthProvider is registered (warning)."""
    aliases = resolve_aliases(root, source)
    links = authorizing_links(root, source, aliases)
    if not links:
        return []
    if registered_provider_signature(root, source, aliases) is not None:
        return []
    line, col = line_col(links[0][1])
    names = sorted(name for name, _ in links)
    return [
        diagnostic(
            "HC-A001",
            "warning",
            path,
            line,
            col,
            f"No AuthProvider registered, but these links declare authorizes=True and "
            f"cannot be verified: {names}. Register a provider, or declare authorizes=False.",
        )
    ]


def check_hc_a002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-A002 — an authorizing link does not reference the provider's derivation (error).

    The guard must derive actor identity via the registered provider's derivation
    expression. Until honest-persist's guarded_mutation guard DSL exists, this checks
    the link body references the derivation name; it tightens to the guard later.
    """
    aliases = resolve_aliases(root, source)
    links = authorizing_links(root, source, aliases)
    if not links:
        return []
    signature = registered_provider_signature(root, source, aliases)
    if signature is None or signature == "":
        # None: HC-A001 handles it. '': literal (no-auth) derivation — nothing to reference.
        return []
    out: list[Diagnostic] = []
    for name, node in links:
        body = node.child_by_field_name("body")
        referenced = body is not None and any(
            sub.type == "identifier" and node_text(sub, source) == signature
            for sub in walk(body)
        )
        if referenced:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-A002",
                "error",
                path,
                line,
                col,
                f"Link '{name}' declares authorizes=True but its guard does not reference "
                f"the registered provider's derivation expression '{signature}'. Actor "
                "identity must be derived inside the guard, not trusted from input.",
            )
        )
    return out


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


def check_hc010(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC010 — a link declares emission of a type its body never produces (warning)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        if "emits" not in kw:
            continue
        emits = vocab_expr_type_names(kw["emits"], source, vocab_defs)
        accepts = vocab_expr_type_names(kw.get("accepts"), source, vocab_defs)
        new_emits = emits - accepts
        if not new_emits:
            continue
        binds = kw.get("binds")
        if binds is None or binds.type != "identifier" or node_text(binds, source) not in bindings:
            continue  # cannot reverse-map slot->type without the paired binding
        reverse = {slot: type_name for type_name, slot in bindings[node_text(binds, source)]["table"].items()}
        produced = {reverse[key] for key in _produced_slot_keys(node, source) if key in reverse}
        phantom = new_emits - produced
        if not phantom:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC010",
                "warning",
                path,
                line,
                col,
                f"Link '{function_name(node, source)}' declares emission of types never "
                f"produced: {sorted(phantom)}.",
            )
        )
    return out


def check_hc004(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC004 — a base type is defined in a vocabulary but never bound or composed (warning)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        table = bindings[binding_var]["table"]
        line, col = vocab["location"]
        for type_name in vocab["base"]:
            in_binding = type_name in table
            in_composed = any(
                type_name in record["requires"] or type_name == record["captures"]
                for record in vocab["composed"]
            )
            if in_binding or in_composed:
                continue
            key = (vocab_var, binding_var, type_name)
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC004", "warning", path, line, col,
                f"Type '{type_name}' defined in vocabulary '{vocab_var}' but never bound or composed."))
    return out


def check_hc005(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC005 — a binding entry names a type that is not in the paired vocabulary (warning)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        binding = bindings[binding_var]
        valid = set(vocab["base"].keys()) | vocab["composed_names"]
        line, col = binding["location"]
        for type_name in binding["table"]:
            if type_name in valid:
                continue
            key = (vocab_var, binding_var, type_name)
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC005", "warning", path, line, col,
                f"Binding '{binding_var}' references type '{type_name}' not found in "
                f"vocabulary '{vocab_var}'."))
    return out


def _recognizer_identity(recognizer):
    """A hashable identity for a recognizer, or None if it cannot be compared statically."""
    kind = recognizer[0]
    if kind == "set":
        return ("set", recognizer[1])
    if kind == "ref":
        return ("ref", recognizer[1])
    return None  # predicates are opaque — treat each as unique, no reuse detection


def check_hc_p014(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P014 — one recognizer is shared by types bound to different slots (field-swap risk)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        table = bindings[binding_var]["table"]
        line, col = vocab["location"]
        recognizer_to_types: dict = {}
        for type_name, recognizer in vocab["base"].items():
            identity = _recognizer_identity(recognizer)
            if identity is None:
                continue
            recognizer_to_types.setdefault(identity, []).append(type_name)
        for identity, type_names in recognizer_to_types.items():
            if len(type_names) < 2:
                continue
            slots = sorted({table[name] for name in type_names if name in table})
            if len(slots) < 2:
                continue
            key = (vocab_var, binding_var, tuple(sorted(type_names)))
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC-P014", "error", path, line, col,
                f"One recognizer is shared by types {sorted(type_names)} bound to distinct "
                f"slots {slots}. Give each slot a semantically distinct recognizer, or the "
                "chain contract cannot catch a swap between them."))
    return out


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


def check_hc_or003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-OR003 — two orchestrators share a run of consecutive operations (warning, soft)."""
    functions = functions_by_name(root, source)
    orchestrators = {
        name: node for name, node in functions.items() if function_role(node, source) == "orchestrator"
    }
    sequences = {
        name: _orchestrator_call_sequence(node, source) for name, node in orchestrators.items()
    }
    out: list[Diagnostic] = []
    for first, second in combinations(sorted(orchestrators), 2):
        run = _longest_common_run(sequences[first], sequences[second])
        if run < _OR003_MIN_RUN:
            continue
        line, col = line_col(orchestrators[first])
        out.append(
            diagnostic(
                "HC-OR003",
                "warning",
                path,
                line,
                col,
                f"Orchestrators '{first}' and '{second}' share {run} consecutive operations. "
                "Consider extracting the shared sequence as a pure helper (if side-effect-free) "
                "or a chain (if I/O is involved). Orchestrators are not composable (HC-OR001).",
            )
        )
    return out


def check_hc008(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC008 — a non-boundary @link performs I/O or non-deterministic work (warning).

    The framework-tier companion to HC-P004: links are the I/O-adjacent layer, so an
    impure link gets a warning nudging boundary=True. HC-P004 still raises the
    principle-tier error on the offending call.
    """
    aliases = resolve_aliases(root, source)
    io = IO_WATCH_LIST["python"]
    nondeterministic = NONDETERMINISTIC_WATCH_LIST["python"]
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        if "boundary" in kw and node_text(kw["boundary"], source) == "True":
            continue
        body = node.child_by_field_name("body")
        hits = sorted(
            {
                name
                for sub in walk(body)
                if sub.type == "call"
                for name in [_qualified_call_name(sub, source)]
                if matches_watchlist(name, io) or matches_watchlist(name, nondeterministic)
            }
        )
        if not hits:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC008",
                "warning",
                path,
                line,
                col,
                f"Link '{function_name(node, source)}' may be impure: {hits}. "
                "Add boundary=True if the I/O is intentional.",
            )
        )
    return out


_HTTP_RESPONSE_MARKERS = frozenset(
    {
        "Response", "JSONResponse", "HTMLResponse", "PlainTextResponse",
        "RedirectResponse", "StreamingResponse", "FileResponse",
    }
)


def check_hc_p017(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P017 — function produces HTTP output but is not a @link with emits (error)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        body = node.child_by_field_name("body")
        marker = None
        for sub in walk(body):
            if sub.type == "call" and _call_name(sub, source) in _HTTP_RESPONSE_MARKERS:
                marker = _call_name(sub, source)
                break
        if marker is None:
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is not None and "emits" in keyword_args(decorator, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P017",
                "error",
                path,
                line,
                col,
                f"Function '{function_name(node, source)}' produces HTTP output "
                f"('{marker}') without being a declared @link with emits vocabulary. "
                "Declare emits covering status, content-type, and body shape, or "
                "delegate to a serializer link.",
            )
        )
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


def check_hc006(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC006 — a composed type's requires/captures names a base type not in the vocabulary."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        base_names = set(vocabulary_base_types(call, source).keys())
        for composed in extract_composed_types(call, source, aliases):
            line, col = composed["location"]
            for required in sorted(composed["requires"]):
                if required not in base_names:
                    out.append(diagnostic("HC006", "error", path, line, col,
                        f"Composed type '{composed['name']}' requires unknown base type '{required}'."))
            captures = composed["captures"]
            if captures is not None and captures not in base_names:
                out.append(diagnostic("HC006", "error", path, line, col,
                    f"Composed type '{composed['name']}' captures unknown base type '{captures}'."))
    return out


def check_hc009(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC009 — a predicate may throw on non-matching input (warning)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        for type_name, recognizer in vocabulary_base_types(call, source).items():
            if recognizer[0] != "predicate":
                continue
            risky = _risky_predicate_ops(recognizer[1], source)
            if not risky:
                continue
            line, col = line_col(recognizer[1])
            out.append(
                diagnostic(
                    "HC009",
                    "warning",
                    path,
                    line,
                    col,
                    f"Predicate '{type_name}' may throw on non-matching input: "
                    f"{sorted(risky)}. Guard the access or wrap in try/except.",
                )
            )
    return out


def check_hc011(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC011 — catch-all recognizer. Sets are bounded; predicates defer to honest-test.

    A Set recognizer is bounded by construction and can never be a catch-all, so it
    is clean. Detecting a catch-all predicate requires sampling the predicate
    (section 4.1) — that is a runtime check, so honest-check emits an info routing
    it to honest-test (section 4.3) rather than evaluating arbitrary code.
    """
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        for type_name, recognizer in vocabulary_base_types(call, source).items():
            if recognizer[0] != "predicate":
                continue
            line, col = line_col(recognizer[1])
            out.append(
                diagnostic(
                    "HC011",
                    "info",
                    path,
                    line,
                    col,
                    f"Catch-all check for predicate type '{type_name}' requires sampling "
                    "and is verified by honest-test.",
                )
            )
    return out


# Registry. Order is report order; each entry is one rule function (section 8).
_ALL_CHECKS = (
    check_hc001,
    check_hc002,
    check_hc003,
    check_hc004,
    check_hc005,
    check_hc006,
    check_hc007,
    check_hc008,
    check_hc010,
    check_hc_p014,
    check_hc009,
    check_hc011,
    check_hc_a001,
    check_hc_a002,
    check_hc_p015,
    check_hc_or001,
    check_hc_or003,
    check_hc_p017,
    check_hc_r001,
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
