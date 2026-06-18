"""Rule registry and the check_source entry point (sections 4, 8).

Each rule is a pure function `check(root_node, source_bytes, path) -> list[Diagnostic]`.
Rules are registered in `_ALL_CHECKS`; `check_source` parses once, short-circuits on
a syntax error (HC-SYN), then runs every registered rule. New rules are added by
writing the function and appending it to the registry — a row, not a branch.

This unit implements the two structural rules that make class-based smuggling and
value-dispatch chains impossible to represent: HC-P003 (class declaration) and
HC-P001 (if/elif/else dispatch). Both cite honest-check-architecture.md section 4.2.
"""

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


def check_hc_p004(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P004 — I/O or non-determinism inside a non-boundary function (error)."""
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


# Registry. Order is report order; each entry is one rule function (section 8).
_ALL_CHECKS = (
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
