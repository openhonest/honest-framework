"""HC-P* Honest-Code structural rules (honest-check-architecture.md section 4.2).

The language-agnostic Honest-Code principles in their Python form: no class smuggling,
no value-dispatch chains, no hidden state, I/O only at declared boundaries.
"""

from honest_check.declgraph import function_name
from honest_check.diagnostics import (
    Diagnostic,
    diagnostic,
)
from honest_check.watchlists import (
    IO_WATCH_LIST,
    NONDETERMINISTIC_WATCH_LIST,
    matches_watchlist,
)
from honest_parse import (
    line_col,
    node_text,
    walk,
)
from honest_check._rule_helpers import (
    _ALLOWED_CLASS_BASES,
    _CACHE_DECORATORS,
    _DISPATCH_BRANCH_THRESHOLD,
    _DYNAMIC_IMPORT_CALLS,
    _IMMUTABLE_MAPPINGS,
    _LIFECYCLE_HOOKS,
    _UNBOUNDED_CALL_BUILTINS,
    _call_name,
    _check_global_reads,
    _class_base_names,
    _class_methods,
    _decorator_name,
    _decorators,
    _direct_nonlocal_names,
    _enclosing_function,
    _equality_target,
    _has_except_clause,
    _has_profiling_evidence,
    _if_chain_conditions,
    _is_boundary_function,
    _mutable_module_containers,
    _qualified_call_name,
    _rebinds_name,
    _self_attr_writes,
    _simple_base_name,
    _string_positional,
    _typeddict_names,
)


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


def check_hc_p010(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P010 — a function returns a non-serializable class instance (section 4.2). A return whose
    value constructs a class (a PascalCase constructor call) that is not a TypedDict declared in this
    file is flagged: the pure interior returns serializable data — a dict or TypedDict — not an object.
    The constructor is recognised however it is written: `Response(...)` and `responses.Response(...)`
    are the same construction, so import style cannot decide whether the rule applies. A declared I/O
    boundary is exempt — converting a value into the outside world's own type is precisely what a
    boundary is for, and the rule governs the pure interior."""
    typeddicts = _typeddict_names(root, source)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "return_statement":
            continue
        values = node.named_children
        if not values or values[0].type != "call":
            continue
        qualified = _qualified_call_name(values[0], source)
        if not qualified:
            continue
        name = qualified.rsplit(".", 1)[-1]
        if not name[:1].isupper() or name in typeddicts or name in _IMMUTABLE_MAPPINGS:
            continue
        enclosing = _enclosing_function(node)
        if enclosing is not None and _is_boundary_function(enclosing, source):
            continue
        line, col = line_col(node)
        out.append(diagnostic("HC-P010", "error", path, line, col,
            f"Return value constructs '{name}', a non-serializable object. The pure interior returns "
            "a dict or TypedDict, not a class instance; if this is an I/O boundary, declare it "
            "(@boundary or @link(boundary=True))."))
    return out


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


def check_hc_p018(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P018 — unbounded call target: a call whose callee set cannot be bounded to a finite,
    statically-visible set. eval/exec run code chosen at runtime; import by a runtime string produces a
    callable from an unbounded module; getattr dispatch with a runtime attribute name resolves an
    unbounded callee. Bounded forms — a named call, a closed-set dict dispatch, a literal getattr or a
    literal import — are left alone. The gate-force realisation of finite-testability.md (its section 6):
    rejecting the unbounded call target is what keeps the reaching-domain locally computable."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call":
            continue
        name = _call_name(node, source)
        if name in _UNBOUNDED_CALL_BUILTINS:
            line, col = line_col(node)
            out.append(diagnostic("HC-P018", "error", path, line, col, f"Call to '{name}' runs code chosen at runtime — an unbounded call target. Dispatch over a declared closed set (a dict table) instead."))
            continue
        if name in _DYNAMIC_IMPORT_CALLS and not _string_positional(node, 0):
            line, col = line_col(node)
            out.append(diagnostic("HC-P018", "error", path, line, col, f"'{name}' imports a module named by a runtime string — an unbounded call target. Import a fixed module, or dispatch over a declared closed set."))
            continue
        function = node.child_by_field_name("function")
        if function.type != "call" or _call_name(function, source) != "getattr":
            continue
        if not _string_positional(function, 1):
            line, col = line_col(node)
            out.append(diagnostic("HC-P018", "error", path, line, col, "Dispatch through getattr with a runtime attribute name is an unbounded call target. Dispatch over a declared closed set (a dict table) instead."))
    return out


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
