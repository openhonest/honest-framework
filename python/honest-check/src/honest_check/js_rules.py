"""JavaScript structural rules (spec section 5).

The Honest Code principles are language-agnostic; honest-check enforces them over each target
language's tree-sitter grammar. This module implements their JavaScript form over
tree-sitter-javascript nodes. The first rule is HC-P003 (class declaration): a JavaScript class is
honest only as a subclass of Error (a thrown fault), the same exemption Python gives Exception
subclasses. Every other class — bare or extending anything else — smuggles state and behaviour into
an object and is rejected.

Pure: each rule is `check(root_node, source_bytes, path) -> list[Diagnostic]`, the same contract as
the Python rules in rules.py. The honest-type-specific rules (vocabularies, chains, links) do not
apply to vanilla JavaScript and are not implemented here.
"""

from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.watchlists import IO_WATCH_LIST, NONDETERMINISTIC_WATCH_LIST, matches_watchlist
from honest_parse import line_col, node_text, walk

# Section 5.4 — I/O and non-determinism reachable only through the `new` form (constructors), which the
# call-name watch lists (watchlists.py) do not cover.
_JS_IO_CONSTRUCTORS = frozenset({"XMLHttpRequest", "WebSocket", "EventSource"})
_JS_NONDETERMINISTIC_CONSTRUCTORS = frozenset({"Date"})

# Section 4.2 — the nondeterministic JavaScript watch-list entries that are non-deterministic on
# *read*, not on call: reading process.env, the browser location/navigator, or document.cookie yields
# a value that depends on environment or session, so a non-boundary function that reads one is impure
# even though no call is made. (`path.*` and `Symbol.for` from the spec list carry a "when used for
# I/O"/"when the key is computed" caveat that plain name-matching cannot honour without false
# positives on pure code — like Python's caveated `hash` entry — so they are deliberately omitted.)
_JS_NONDETERMINISTIC_READS = frozenset(
    {
        "process.env", "process.pid", "process.argv", "process.platform", "process.version",
        "navigator.*", "location.*", "document.cookie",
    }
)

# Section 5.3 — the only base a JavaScript class may extend (a thrown fault). Everything else,
# including a bare class implicitly extending Object, is inheritance and is rejected.
_ALLOWED_JS_CLASS_BASES = frozenset({"Error"})

# Section 4.2 / 5.1 — the minimum branch count for an if/else-if chain to count as value dispatch.
_JS_DISPATCH_BRANCH_THRESHOLD = 3

# The JavaScript function node types — each opens a new scope.
_JS_FUNCTION_TYPES = (
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
    "generator_function_declaration",
    "generator_function",
)

# Section 5.6 — cache constructs that are caches by nature. A WeakMap's only use is associating data
# with objects (memoization); memoize/memoizeOne are explicit caches. A bare `new Map()` is a
# general-purpose collection and is not flagged (see the spec: "used as cache" is not statically decidable).
_JS_CACHE_CONSTRUCTORS = frozenset({"WeakMap"})
_JS_CACHE_CALLS = frozenset({"memoize", "memoizeOne"})

# Section 5.7 — framework lifecycle hooks. Their presence wires behaviour to a hidden lifecycle
# instead of to server-rendered HTML / HTMX attributes (honest-DOM anti-patterns, honest-DOM §6).
_JS_LIFECYCLE_HOOKS = frozenset(
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


def _is_class_node(node) -> bool:
    """Whether a node is a JavaScript class definition: a named `class_declaration`, or an anonymous
    `class` expression (distinguished from the `class` keyword token by carrying a body)."""
    if node.type == "class_declaration":
        return True
    return node.type == "class" and node.child_by_field_name("body") is not None


def _class_name(node, source: bytes) -> str:
    """The declared name of a JavaScript class, or '<anonymous>' for a class expression."""
    name = node.child_by_field_name("name")
    return node_text(name, source) if name is not None else "<anonymous>"


def _class_base(node, source: bytes):
    """The superclass name of a JavaScript class (the expression after `extends`), or None when the
    class declares no heritage."""
    for child in node.children:
        if child.type == "class_heritage":
            named = child.named_children
            return node_text(named[0], source) if named else None
    return None


def check_hc_p003_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P003 (JavaScript) — a class is honest only as a subclass of Error (section 5.3). A bare class
    or one extending anything else is inheritance: use a plain object for data or a pure function."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if not _is_class_node(node):
            continue
        name = _class_name(node, source)
        base = _class_base(node, source)
        line, col = line_col(node)
        if base is None:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' has no declared base. Honest Code permits a JavaScript class only "
                    "as a subclass of Error. Use a plain object for data or a pure function.",
                )
            )
        elif base not in _ALLOWED_JS_CLASS_BASES:
            out.append(
                diagnostic(
                    "HC-P003",
                    "error",
                    path,
                    line,
                    col,
                    f"Class '{name}' inherits from '{base}'. Use composition over inheritance.",
                )
            )
    return out


def _js_call_name(call_node, source: bytes) -> str:
    """The callee name of a JavaScript call: 'foo' for foo(), 'bar' for obj.bar()."""
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return ""
    if fn.type == "member_expression":
        return node_text(fn.child_by_field_name("property"), source)
    return node_text(fn, source)


def _js_cache_construct(node, source: bytes):
    """The cache a node constructs (section 5.6): a WeakMap `new` expression or a memoize/memoizeOne
    call. Returns the construct's name, or None."""
    if node.type == "new_expression":
        constructor = node_text(node.child_by_field_name("constructor"), source)
        if constructor in _JS_CACHE_CONSTRUCTORS:
            return constructor
    if node.type == "call_expression":
        name = _js_call_name(node, source)
        if name in _JS_CACHE_CALLS:
            return name
    return None


def check_hc_p006_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P006 (JavaScript) — a cache construct without profiling evidence (warning, section 5.6). A
    WeakMap and memoize/memoizeOne are caches by nature; profile the path they optimise, or dismiss."""
    out: list[Diagnostic] = []
    for node in walk(root):
        name = _js_cache_construct(node, source)
        if name is None:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P006",
                "warning",
                path,
                line,
                col,
                f"Cache '{name}' detected without profiling evidence. Profile the path it optimises, or dismiss with '// honest: ignore HC-P006'.",
            )
        )
    return out


def check_hc_p011_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P011 (JavaScript) — a framework lifecycle hook (section 5.7). useEffect, addEventListener and
    their kin wire behaviour to a hidden lifecycle; use HTMX attributes or server-rendered HTML."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call_expression":
            continue
        name = _js_call_name(node, source)
        if name not in _JS_LIFECYCLE_HOOKS:
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


def _js_type_check(node, source: bytes):
    """The type-check kind of a node (section 5.5): 'typeof' for a typeof unary, 'instanceof' for an
    instanceof binary, else None."""
    op = node.child_by_field_name("operator")
    if op is None:
        return None
    operator = node_text(op, source)
    if node.type == "unary_expression" and operator == "typeof":
        return "typeof"
    if node.type == "binary_expression" and operator == "instanceof":
        return "instanceof"
    return None


def check_hc_p005_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P005 (JavaScript) — a typeof or instanceof check in business logic (section 5.5). Branching on
    a runtime type is a hidden discriminant; declare a vocabulary and let recognizers classify."""
    out: list[Diagnostic] = []
    for node in walk(root):
        kind = _js_type_check(node, source)
        if kind is None:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P005",
                "warning",
                path,
                line,
                col,
                f"{kind} check in business logic. Consider a vocabulary declaration instead.",
            )
        )
    return out


def _js_equality_target(condition, source: bytes):
    """If `condition` is `IDENT === value` (or ==), return IDENT's text; else None. Unwraps the
    parenthesized condition of a JavaScript if-statement."""
    if condition is None:
        return None
    if condition.type == "parenthesized_expression":
        condition = condition.named_children[0]
    if condition.type != "binary_expression":
        return None
    op = condition.child_by_field_name("operator")
    if op is None or node_text(op, source) not in ("===", "=="):
        return None
    left = condition.child_by_field_name("left")
    if left is None or left.type != "identifier":
        return None
    return node_text(left, source)


def _js_else_if(if_node):
    """The nested if-statement of an `else if`, or None for a plain else or no else."""
    alt = if_node.child_by_field_name("alternative")
    if alt is None or alt.type != "else_clause":
        return None
    inner = alt.named_children
    if inner and inner[0].type == "if_statement":
        return inner[0]
    return None


def _js_if_chain_conditions(if_node):
    """Every condition guarding a branch of an if/else-if chain: the if plus each else-if."""
    conditions = []
    node = if_node
    while node is not None:
        conditions.append(node.child_by_field_name("condition"))
        node = _js_else_if(node)
    return [c for c in conditions if c is not None]


def check_hc_p001_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P001 (JavaScript) — an if/else-if chain dispatching on a single value (section 5.1). Three or
    more branches comparing the same identifier to constants is a dict lookup written as control flow."""
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "if_statement":
            continue
        if node.parent is not None and node.parent.type == "else_clause":
            continue  # a nested else-if, already counted as part of its enclosing chain
        targets = [t for t in (_js_equality_target(c, source) for c in _js_if_chain_conditions(node)) if t is not None]
        if len(targets) < _JS_DISPATCH_BRANCH_THRESHOLD:
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
                "if/else-if chain dispatches on value — use dict lookup. See honest-code-principles.md §3.",
            )
        )
    return out


def _js_scope_nodes(node):
    """Yield `node` and its descendants without descending into nested function scopes — the nodes of
    a single function's own scope."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        for child in current.children:
            if child.type not in _JS_FUNCTION_TYPES:
                stack.append(child)


def _js_mutable_decl_names(decl_node, source: bytes) -> set:
    """The identifier names a let/var declaration binds. Empty for const — a const binding cannot be
    reassigned, so it cannot carry mutable closure state."""
    if decl_node.type == "lexical_declaration" and decl_node.children and decl_node.children[0].type == "const":
        return set()
    names = set()
    for child in decl_node.named_children:
        name = child.child_by_field_name("name")
        if name is not None and name.type == "identifier":
            names.add(node_text(name, source))
    return names


def _js_param_names(func_node, source: bytes) -> set:
    """The identifier parameter names of a function (single-arrow parameter or a parameter list)."""
    names = set()
    single = func_node.child_by_field_name("parameter")
    if single is not None and single.type == "identifier":
        names.add(node_text(single, source))
    params = func_node.child_by_field_name("parameters")
    if params is not None:
        for child in params.named_children:
            if child.type == "identifier":
                names.add(node_text(child, source))
    return names


def _js_scope_lets(func_node, source: bytes) -> set:
    """The let/var names declared in a function's own scope (not nested functions)."""
    names = set()
    body = func_node.child_by_field_name("body")
    if body is None:
        return names
    for node in _js_scope_nodes(body):
        if node.type in ("lexical_declaration", "variable_declaration"):
            names |= _js_mutable_decl_names(node, source)
    return names


def _js_reassigned_names(func_node, source: bytes) -> set:
    """The identifier names reassigned (=, +=/-=/…, ++/--) in a function's own scope (not nested)."""
    names = set()
    body = func_node.child_by_field_name("body")
    if body is None:
        return names
    for node in _js_scope_nodes(body):
        if node.type in ("assignment_expression", "augmented_assignment_expression"):
            left = node.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                names.add(node_text(left, source))
        elif node.type == "update_expression":
            argument = node.child_by_field_name("argument")
            if argument is not None and argument.type == "identifier":
                names.add(node_text(argument, source))
    return names


def check_hc_p016_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P016 (JavaScript) — a nested function captures an enclosing let/var and reassigns it (section
    4.2 / 5.x). Closures are the non-class vector for smuggling mutable state; use pure parameters or
    move the state into persist. A binding the inner function shadows (its own let/var or a parameter)
    is not a capture."""
    out: list[Diagnostic] = []
    for outer in walk(root):
        if outer.type not in _JS_FUNCTION_TYPES:
            continue
        outer_lets = _js_scope_lets(outer, source)
        if not outer_lets:
            continue
        for inner in walk(outer):
            if inner is outer or inner.type not in _JS_FUNCTION_TYPES:
                continue
            shadowed = _js_scope_lets(inner, source) | _js_param_names(inner, source)
            captured = (_js_reassigned_names(inner, source) & outer_lets) - shadowed
            if not captured:
                continue
            line, col = line_col(inner)
            out.append(
                diagnostic(
                    "HC-P016",
                    "error",
                    path,
                    line,
                    col,
                    f"Inner function captures {sorted(captured)} via closure and mutates it. Closures may "
                    "not carry mutable state — use pure parameters or move state into persist.",
                )
            )
    return out


def _js_qualified_name(node, source: bytes) -> str:
    """The dotted name of a callee: 'fetch' for an identifier, 'console.log' for a member expression,
    'a.b.c' for a chain. '' for a computed member, a call result, or any other callee shape."""
    if node.type == "identifier":
        return node_text(node, source)
    if node.type == "member_expression":
        return _js_qualified_name(node.child_by_field_name("object"), source) + "." + node_text(node.child_by_field_name("property"), source)
    return ""


def _js_reads_impure(node, source: bytes) -> bool:
    """True if this member_expression reads a nondeterministic slot (process.env, location.*, …). A
    member that is the callee of a call is excluded: that is a call, trapped by the call branch, so
    excluding it keeps navigator.sendBeacon() from being flagged twice. A member expression is always
    nested, so it always has a parent; only a call parent carries a `function` field to compare."""
    if not matches_watchlist(_js_qualified_name(node, source), _JS_NONDETERMINISTIC_READS):
        return False
    callee = node.parent.child_by_field_name("function")
    return callee is None or (callee.start_byte, callee.end_byte) != (node.start_byte, node.end_byte)


def _js_impure_name(node, source: bytes):
    """The watched name of a node that performs I/O or non-deterministic work (section 5.4): the dotted
    name of a matching call, 'new X()' for a matching constructor, or a nondeterministic member read
    (process.env, location.*, document.cookie). None otherwise."""
    if node.type == "call_expression":
        name = _js_qualified_name(node.child_by_field_name("function"), source)
        if matches_watchlist(name, IO_WATCH_LIST["javascript"]) or matches_watchlist(name, NONDETERMINISTIC_WATCH_LIST["javascript"]):
            return name
    if node.type == "new_expression":
        constructor = node_text(node.child_by_field_name("constructor"), source)
        if constructor in _JS_IO_CONSTRUCTORS or constructor in _JS_NONDETERMINISTIC_CONSTRUCTORS:
            return f"new {constructor}()"
    if node.type == "member_expression" and _js_reads_impure(node, source):
        return _js_qualified_name(node, source)
    return None


def _js_enclosing_function(node):
    """The nearest enclosing function, or None at module level."""
    current = node.parent
    while current is not None:
        if current.type in _JS_FUNCTION_TYPES:
            return current
        current = current.parent
    return None


def _js_boundary_lines(root, source: bytes) -> set:
    """The 1-based line numbers carrying a `// honest: boundary` comment (section 5.2)."""
    lines = set()
    for node in walk(root):
        if node.type == "comment" and node_text(node, source).lstrip("/# ").startswith("honest: boundary"):
            lines.add(node.start_point[0] + 1)
    return lines


def _js_is_boundary(func_node, boundary_lines) -> bool:
    """A function is a boundary if a `// honest: boundary` comment sits on its line or the line above it."""
    start_line = func_node.start_point[0] + 1
    return start_line in boundary_lines or start_line - 1 in boundary_lines


def check_hc_p004_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P004 (JavaScript) — I/O or non-deterministic work inside a non-boundary function (section 5.4).
    Move it to a boundary (mark the function `// honest: boundary`), or it cannot be verified for purity."""
    boundary_lines = _js_boundary_lines(root, source)
    out: list[Diagnostic] = []
    for node in walk(root):
        name = _js_impure_name(node, source)
        if name is None:
            continue
        enclosing = _js_enclosing_function(node)
        if enclosing is None or _js_is_boundary(enclosing, boundary_lines):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P004",
                "error",
                path,
                line,
                col,
                f"'{name}' performs I/O or non-deterministic work inside a non-boundary function. "
                "Mark the function '// honest: boundary', or it cannot be verified for purity.",
            )
        )
    return out


def check_hc_p002_js(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P002 (JavaScript) — an exception caught inside a non-boundary function (section 5.2). Business
    logic raises; the boundary catches. A try/finally with no catch is cleanup and is allowed."""
    boundary_lines = _js_boundary_lines(root, source)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "try_statement" or node.child_by_field_name("handler") is None:
            continue
        enclosing = _js_enclosing_function(node)
        if enclosing is None or _js_is_boundary(enclosing, boundary_lines):
            continue
        line, col = line_col(node)
        enclosing_name = enclosing.child_by_field_name("name")
        function_label = node_text(enclosing_name, source) if enclosing_name is not None else "<anonymous>"
        out.append(
            diagnostic(
                "HC-P002",
                "error",
                path,
                line,
                col,
                f"Function '{function_label}' catches an exception in business logic. Let it raise and "
                "catch at the boundary (a '// honest: boundary' function), or return a fault as data.",
            )
        )
    return out
