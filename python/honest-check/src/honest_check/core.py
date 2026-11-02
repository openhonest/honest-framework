"""check_source — the pure core of the checker (sections 3.3, 3.4, 4.1).

It parses one source unit under the grammar honest-parse detects from the path's
extension, resolves the framework's own construction call sites, builds the declaration
graph, and runs the rules this layer owns over that graph, returning findings as data. It
opens no file, executes no application code, and never raises for a violation: a violation
comes back as a Diagnostic.

The rule engine is data inside this function — nested resolvers, nested per-construct
handlers, and the module-level tables below — never a module-level per-rule def. The exact
Diagnostic each rule produces is pinned by the conformance suite (section 9.2), not by a
separately declared function.
"""

import ast
import itertools

from honest_parse import line_col, parse_source, walk

# A class is permitted only as a subclass of one of these (section 4.1, HC-P003). A bare
# class implicitly inherits object, which is not approved, so it is a violation.
_APPROVED_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)

# The framework construction call sites this layer recognizes as top-level constructs
# (section 4.1). composed() is not here: it is only meaningful inside a vocabulary's
# composed_types, where the vocabulary handler reaches it, so a standalone composed() call
# in the walk is skipped rather than processed twice.
_CONSTRUCTORS = frozenset({"vocabulary", "chain", "state_machine"})

# The absence atoms a declared return may name (§HC-R004): the same word a union uses for an
# env that may be missing. A card naming either says the answer may be absent.
_ABSENCE_ATOMS = frozenset({"NOTHING", "Absent"})

# The node types that open an inner scope. A return, a yield or a call inside one of these
# belongs to that inner function, so cross_declaration's bounded body search stops here
# (sections 4.2, §HC-R004, §HC-R005).
_INNER_SCOPES = frozenset({"function_definition", "lambda", "decorated_definition"})

# The framework lifecycle hooks HC-P011 names (§4.2). A call to any of these declares a
# client-side initialization sequence the framework decides the order of; the honest form is
# an HTMX attribute or server-rendered HTML that arrives ready.
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

# The Python I/O calls HC-P004 names in a non-boundary function (§5.4). _IO_CALLS is matched
# by whole dotted name (`open`, `print`, `os.system`); _IO_MODULE_PREFIXES is the three
# modules whose every call reaches outside the process, matched by dotted prefix.
_IO_CALLS = frozenset({"open", "print", "os.system"})
_IO_MODULE_PREFIXES = ("requests.", "urllib.", "subprocess.")

# The runtime type checks HC-P005 names in a non-boundary function (§5.5): a hand-written
# check that duplicates a constraint a vocabulary should declare at the boundary.
_TYPE_CHECK_CALLS = frozenset({"isinstance", "type"})

# The cache decorators HC-P006 names (§5.6). A function carrying one with no profiling note
# has no evidence the cache was measured, so the cache cannot be shown warranted.
_CACHE_DECORATORS = frozenset({"lru_cache", "cache", "cached_property", "memoize"})


def check_source(source, path, rule_config):
    parsed = parse_source(source.encode("utf-8"), path)
    if "ok" not in parsed:
        error = parsed["err"]

        def syntax_location():
            detail = error.get("detail", {})
            line = detail.get("line", 1)
            col = detail.get("col", 1)
            return f"{path}:{line}:{col}"

        if error.get("code") == "syntax_error":
            return [
                {
                    "rule_id": "HC-SYN",
                    "severity": "error",
                    "message": error.get("message", "source does not parse"),
                    "source_location": syntax_location(),
                    "context": "",
                    "fixable": False,
                }
            ]
        return []

    root = parsed["ok"].root_node
    nodes = walk(root)

    def diagnostic(rule_id, severity, message, node):
        line, col = line_col(node)
        return {
            "rule_id": rule_id,
            "severity": severity,
            "message": message,
            "source_location": f"{path}:{line}:{col}",
            "context": node.text.decode("utf-8", "replace").splitlines()[0]
            if node.text
            else "",
            "fixable": False,
        }

    def literal_string(node):
        """The Python string a `string` node spells, quotes stripped."""
        return ast.literal_eval(node.text.decode("utf-8"))

    def string_members(node):
        """The string values a set/list/tuple node holds, in source order."""
        return [
            literal_string(child)
            for child in node.named_children
            if child.type == "string"
        ]

    def call_arguments(call_node):
        """The (positional nodes, keyword name -> value node) of a call."""
        argument_list = call_node.child_by_field_name("arguments")
        positionals = []
        keywords = {}
        if argument_list is None:
            return positionals, keywords
        for child in argument_list.named_children:
            if child.type == "keyword_argument":
                name = child.child_by_field_name("name").text.decode("utf-8")
                keywords[name] = child.child_by_field_name("value")
            else:
                positionals.append(child)
        return positionals, keywords

    def resolve_aliases():
        """Map each local name bound by a honest_type import to its canonical constructor
        name (section 3.3), so a call under an alias resolves to the real constructor."""
        aliases = {}
        for node in nodes:
            if node.type != "import_from_statement":
                continue
            module = node.child_by_field_name("module_name")
            if module is None or module.text.decode("utf-8") != "honest_type":
                continue
            for imported in node.children_by_field_name("name"):
                if imported.type == "aliased_import":
                    canonical = imported.child_by_field_name("name").text.decode("utf-8")
                    local = imported.child_by_field_name("alias").text.decode("utf-8")
                    aliases[local] = canonical
                else:
                    name = imported.text.decode("utf-8")
                    aliases[name] = name
        return aliases

    aliases = resolve_aliases()

    def canonical_name(call_node):
        """The constructor name a call resolves to, or None when the call is not a framework
        constructor. A direct constructor-name call counts, and an aliased one resolves
        through the import (section 3.3)."""
        function = call_node.child_by_field_name("function")
        if function is None or function.type != "identifier":
            return None
        name = function.text.decode("utf-8")
        if name in aliases:
            return aliases[name]
        if name in _CONSTRUCTORS:
            return name
        return None

    def base_types_of(dictionary_node):
        """The base-type map of a vocabulary's first argument: name -> (kind, members).
        kind is 'set' with a frozenset of members, or 'predicate' with None (a lambda or any
        other opaque recognizer honest-check cannot run)."""
        base_types = {}
        for pair in dictionary_node.named_children:
            if pair.type != "pair":
                continue
            name = literal_string(pair.child_by_field_name("key"))
            value = pair.child_by_field_name("value")
            if value.type == "set":
                base_types[name] = ("set", frozenset(string_members(value)))
            else:
                base_types[name] = ("predicate", None)
        return base_types

    def check_vocabulary(call_node):
        """HC003 overlap, HC011 catch-all predicate, and HC006 unknown composed base
        (section 4.1)."""
        findings = []
        positionals, keywords = call_arguments(call_node)
        if not positionals or positionals[0].type != "dictionary":
            return findings
        base_types = base_types_of(positionals[0])

        for a, b in itertools.combinations(base_types, 2):
            kind_a, members_a = base_types[a]
            kind_b, members_b = base_types[b]
            if kind_a == "set" and kind_b == "set":
                overlap = members_a & members_b
                if overlap:
                    findings.append(
                        diagnostic(
                            "HC003",
                            "error",
                            f"Types {a!r} and {b!r} share values: {sorted(overlap)}",
                            call_node,
                        )
                    )
            else:
                findings.append(
                    diagnostic(
                        "HC003",
                        "info",
                        f"Types {a!r} and {b!r} may overlap on a value — "
                        "verified by honest-test",
                        call_node,
                    )
                )

        for name, (kind, _members) in base_types.items():
            if kind == "predicate":
                findings.append(
                    diagnostic(
                        "HC011",
                        "info",
                        f"Predicate recognizer {name!r} may be a catch-all — "
                        "verified by honest-test",
                        call_node,
                    )
                )

        composed_list = keywords.get("composed_types")
        if composed_list is not None:
            for child in composed_list.named_children:
                if child.type == "call" and canonical_name(child) == "composed":
                    findings.extend(check_composed(child, base_types))
        return findings

    def check_composed(call_node, base_types):
        """HC006: a composed type whose requires or captures names a base the vocabulary does
        not declare (section 4.1)."""
        findings = []
        positionals, _keywords = call_arguments(call_node)
        if len(positionals) < 2 or positionals[1].type != "dictionary":
            return findings
        for pair in positionals[1].named_children:
            if pair.type != "pair":
                continue
            required = literal_string(pair.child_by_field_name("key"))
            if required not in base_types:
                findings.append(
                    diagnostic(
                        "HC006",
                        "error",
                        f"Composed type requires unknown base type {required!r}",
                        call_node,
                    )
                )
        if len(positionals) >= 3 and positionals[2].type == "string":
            captured = literal_string(positionals[2])
            if captured not in base_types:
                findings.append(
                    diagnostic(
                        "HC006",
                        "error",
                        f"Composed type captures unknown base type {captured!r}",
                        call_node,
                    )
                )
        return findings

    def check_chain(call_node):
        """HC007: a chain() constructed with no links is empty (section 4.1)."""
        positionals, _keywords = call_arguments(call_node)
        if not positionals:
            return [diagnostic("HC007", "error", "Chain has no links", call_node)]
        return []

    def check_state_machine(call_node):
        """HC-SM01/02/05: a transition state or event, or the initial state, not in its
        vocabulary (section 4.1)."""
        findings = []
        positionals, _keywords = call_arguments(call_node)
        if len(positionals) < 4:
            return findings
        states = set(string_members(positionals[0]))
        events = set(string_members(positionals[1]))
        transitions = positionals[2]
        initial = literal_string(positionals[3]) if positionals[3].type == "string" else None

        for pair in transitions.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key.type != "tuple":
                continue
            members = string_members(key)
            if len(members) < 2:
                continue
            state, event = members[0], members[1]
            if state not in states:
                findings.append(
                    diagnostic(
                        "HC-SM01",
                        "error",
                        f"State {state!r} in transition table not in states vocabulary",
                        call_node,
                    )
                )
            if event not in events:
                findings.append(
                    diagnostic(
                        "HC-SM02",
                        "error",
                        f"Event {event!r} in transition table not in events vocabulary",
                        call_node,
                    )
                )
        if initial is not None and initial not in states:
            findings.append(
                diagnostic(
                    "HC-SM05",
                    "error",
                    f"Initial state {initial!r} not in states vocabulary",
                    call_node,
                )
            )
        return findings

    # The construction dispatch: a call that resolves to a framework constructor runs the
    # matching handler; a call that resolves to no constructor is skipped, the expected and
    # common case for ordinary application calls, not a fault.
    construction_handlers = {
        "vocabulary": check_vocabulary,
        "chain": check_chain,
        "state_machine": check_state_machine,
    }

    def check_classes():
        """HC-P003: a bare class, or a class inheriting a non-approved base (section 4.1)."""
        findings = []
        for node in nodes:
            if node.type != "class_definition":
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<anonymous>"
            superclasses = node.child_by_field_name("superclasses")
            bases = (
                [c for c in superclasses.named_children]
                if superclasses is not None
                else []
            )
            if not bases:
                findings.append(
                    diagnostic(
                        "HC-P003",
                        "error",
                        f"Class {name!r} has no declared base. Use a TypedDict for data "
                        "shapes or a pure function.",
                        node,
                    )
                )
                continue
            for base in bases:
                if base.text.decode("utf-8") not in _APPROVED_BASES:
                    findings.append(
                        diagnostic(
                            "HC-P003",
                            "error",
                            f"Class {name!r} inherits from {base.text.decode('utf-8')!r}. "
                            "Use composition over inheritance.",
                            node,
                        )
                    )
        return findings

    def enclosing_function(node):
        """The nearest enclosing function_definition of a node, climbing parents, or None at
        module scope. A node's nearest enclosing function is the scope that owns it, so a
        nonlocal or a mutation reads as belonging to the function it sits directly inside."""
        parent = node.parent
        while parent is not None:
            if parent.type == "function_definition":
                return parent
            parent = parent.parent
        return None

    def dispatch_variable(condition):
        """The variable name an `if`/`elif` condition dispatches on — the left identifier of an
        `identifier == <value>` equality test — or None when the condition is not that shape
        (§HC-P001)."""
        if condition is None or condition.type != "comparison_operator":
            return None
        if not any(child.type == "==" for child in condition.children):
            return None
        operands = condition.named_children
        if len(operands) != 2 or operands[0].type != "identifier":
            return None
        return operands[0].text.decode("utf-8")

    def check_p001():
        """HC-P001: an if/elif chain of three or more branches that dispatch on one variable's
        value — three or more equality tests on the same variable across if/elif. Reported at
        the `if` statement's line (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "if_statement":
                continue
            conditions = [node.child_by_field_name("condition")]
            for child in node.named_children:
                if child.type == "elif_clause":
                    conditions.append(child.child_by_field_name("condition"))
            variables = [
                variable
                for variable in (dispatch_variable(c) for c in conditions)
                if variable is not None
            ]
            if any(variables.count(variable) >= 3 for variable in set(variables)):
                findings.append(
                    diagnostic(
                        "HC-P001",
                        "error",
                        "if/elif/else chain dispatches on value — use dict lookup. "
                        "See honest-code-principles.md §3.",
                        node,
                    )
                )
        return findings

    def underscore_self_name(target):
        """The attribute name of a `self._name` assignment target whose name starts with an
        underscore, or None when the target is not that shape (§HC-P007)."""
        if target is None or target.type != "attribute":
            return None
        obj = target.child_by_field_name("object")
        attr = target.child_by_field_name("attribute")
        if obj is None or attr is None or obj.type != "identifier":
            return None
        if obj.text.decode("utf-8") != "self":
            return None
        name = attr.text.decode("utf-8")
        if not name.startswith("_"):
            return None
        return name

    def within_class_init(node):
        """True when a node's nearest enclosing function is an `__init__` that is a method of a
        class — the scope HC-P007 reads for hidden instance state (§4.2)."""
        function = enclosing_function(node)
        if function is None:
            return False
        name = function.child_by_field_name("name")
        if name is None or name.text.decode("utf-8") != "__init__":
            return False
        grandparent = function.parent.parent if function.parent is not None else None
        return grandparent is not None and grandparent.type == "class_definition"

    def check_p007():
        """HC-P007: inside a class __init__, an assignment to a `self._name` attribute whose
        name starts with an underscore — hidden instance state. Reported at the assignment's
        line (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "assignment":
                continue
            name = underscore_self_name(node.child_by_field_name("left"))
            if name is None or not within_class_init(node):
                continue
            findings.append(
                diagnostic(
                    "HC-P007",
                    "warning",
                    f"Instance state {name!r}. Pass as parameter or use context manager.",
                    node,
                )
            )
        return findings

    def called_name(call_node):
        """The name a call invokes — a bare identifier, or the final attribute of a dotted
        call such as `window.addEventListener` — or None (§HC-P011)."""
        function = call_node.child_by_field_name("function")
        if function is None:
            return None
        if function.type == "identifier":
            return function.text.decode("utf-8")
        if function.type == "attribute":
            attr = function.child_by_field_name("attribute")
            return attr.text.decode("utf-8") if attr is not None else None
        return None

    def check_p011():
        """HC-P011: a call whose name is a framework lifecycle hook (§4.2). Reported at the
        call's line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            name = called_name(node)
            if name in _LIFECYCLE_HOOKS:
                findings.append(
                    diagnostic(
                        "HC-P011",
                        "error",
                        f"Lifecycle hook {name!r}. Use HTMX attributes or server-rendered "
                        "HTML.",
                        node,
                    )
                )
        return findings

    def own_body(fdef):
        """The body descendants belonging to a function itself, not descending into a deeper
        nested def, lambda or decorated def — those statements are the inner scope's own
        (§4.2). A `nonlocal` and a mutation count only where they sit directly in this body."""
        body = fdef.child_by_field_name("body")
        found = []
        if body is None:
            return found

        def gather(node):
            for child in node.named_children:
                if child.type in _INNER_SCOPES:
                    continue
                found.append(child)
                gather(child)

        gather(body)
        return found

    def nonlocal_names(statements):
        """The names declared by the `nonlocal` statements directly in a function body."""
        names = set()
        for statement in statements:
            if statement.type != "nonlocal_statement":
                continue
            for child in statement.named_children:
                if child.type == "identifier":
                    names.add(child.text.decode("utf-8"))
        return names

    def mutated_names(statements):
        """The names an assignment or augmented assignment targets directly in a function
        body — the left of each `x = ...` or `x += ...` whose target is a plain identifier."""
        names = set()
        for statement in statements:
            if statement.type not in ("assignment", "augmented_assignment"):
                continue
            target = statement.child_by_field_name("left")
            if target is not None and target.type == "identifier":
                names.add(target.text.decode("utf-8"))
        return names

    def check_p016():
        """HC-P016: an inner (nested) function that declares `nonlocal X` and mutates X by
        assignment or augmented assignment. Reported at the inner function's `def` line
        (§4.2)."""
        findings = []
        for node in nodes:
            if node.type != "function_definition" or enclosing_function(node) is None:
                continue
            statements = own_body(node)
            hit = sorted(nonlocal_names(statements) & mutated_names(statements))
            if not hit:
                continue
            name_node = node.child_by_field_name("name")
            inner = name_node.text.decode("utf-8") if name_node else "<anonymous>"
            findings.append(
                diagnostic(
                    "HC-P016",
                    "error",
                    f"Inner function {inner!r} captures {hit[0]!r} via nonlocal and mutates "
                    "it. Closures may not carry mutable state — use pure parameters or move "
                    "state into persist.",
                    node,
                )
            )
        return findings

    def decorators_of(fdef):
        """The decorator nodes applied to a function — the `decorator` children of the
        enclosing `decorated_definition`, or an empty list for an undecorated function. The
        boundary signal HC-P002, HC-P004 and HC-P005 read, and the cache signal HC-P006 reads,
        both live here (§4.2)."""
        parent = fdef.parent
        if parent is None or parent.type != "decorated_definition":
            return []
        return [child for child in parent.children if child.type == "decorator"]

    def decorator_expression(decorator):
        """The expression a decorator applies — the identifier, attribute or call after the
        `@`, or None for an empty decorator node."""
        return decorator.named_children[0] if decorator.named_children else None

    def decorator_target(decorator):
        """The final name a decorator names — `boundary` from `@boundary`, `lru_cache` from
        `@functools.lru_cache(maxsize=1)` — or None when it is neither a plain nor a dotted
        name, called or bare (§4.2, §5.6)."""
        expr = decorator_expression(decorator)
        if expr is not None and expr.type == "call":
            expr = expr.child_by_field_name("function")
        if expr is None:
            return None
        if expr.type == "identifier":
            return expr.text.decode("utf-8")
        if expr.type == "attribute":
            attr = expr.child_by_field_name("attribute")
            return attr.text.decode("utf-8") if attr is not None else None
        return None

    def is_boundary_decorator(decorator):
        """True when a decorator declares its function a boundary — `@boundary` (bare or
        called) or `@link(boundary=True)` (§4.2)."""
        expr = decorator_expression(decorator)
        if expr is None:
            return False
        if expr.type == "identifier":
            return expr.text.decode("utf-8") == "boundary"
        if expr.type == "call":
            function = expr.child_by_field_name("function")
            if function is None or function.type != "identifier":
                return False
            name = function.text.decode("utf-8")
            if name == "boundary":
                return True
            if name != "link":
                return False
            _positionals, keywords = call_arguments(expr)
            value = keywords.get("boundary")
            return value is not None and value.type == "true"
        return False

    def in_non_boundary_function(node):
        """True when a node's nearest enclosing function exists and carries no boundary
        decorator — the scope HC-P002, HC-P004 and HC-P005 fire in (§4.2, §5.4, §5.5). A node
        at module scope, or in a boundary function, is not in a non-boundary function."""
        function = enclosing_function(node)
        if function is None:
            return False
        return not any(is_boundary_decorator(d) for d in decorators_of(function))

    def dotted_target(call_node):
        """The dotted name a call invokes — `open`, `os.system`, `requests.get`,
        `urllib.request.urlopen` — or None when the target is not a plain or dotted name, such
        as a call on a call's result (§5.4)."""

        def name_of(node):
            if node is None:
                return None
            if node.type == "identifier":
                return node.text.decode("utf-8")
            if node.type == "attribute":
                obj = name_of(node.child_by_field_name("object"))
                attr = node.child_by_field_name("attribute")
                if obj is None or attr is None:
                    return None
                return f"{obj}.{attr.text.decode('utf-8')}"
            return None

        return name_of(call_node.child_by_field_name("function"))

    def check_p002():
        """HC-P002: a `try` with an `except` clause inside a non-boundary function — business
        logic that swallows a fault instead of letting it raise to the boundary (§4.2, §5.2).
        A `try`/`finally` with no `except` does not fire. Reported at the `try`'s line."""
        findings = []
        for node in nodes:
            if node.type != "try_statement":
                continue
            if not any(child.type == "except_clause" for child in node.named_children):
                continue
            if not in_non_boundary_function(node):
                continue
            function = enclosing_function(node)
            name_node = function.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<anonymous>"
            findings.append(
                diagnostic(
                    "HC-P002",
                    "error",
                    f"Function {name!r} catches an exception in business logic. Let the "
                    "function raise; catch at the boundary (@boundary / route handler), or "
                    "return a fault as data.",
                    node,
                )
            )
        return findings

    def check_p004():
        """HC-P004: a call to Python I/O in a non-boundary function (§5.4) — a whole-name hit
        on _IO_CALLS or a dotted-prefix hit on _IO_MODULE_PREFIXES. Reported at the call's
        line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            target = dotted_target(node)
            if target is None:
                continue
            is_io = target in _IO_CALLS or any(
                target.startswith(prefix) for prefix in _IO_MODULE_PREFIXES
            )
            if not is_io or not in_non_boundary_function(node):
                continue
            findings.append(
                diagnostic(
                    "HC-P004",
                    "error",
                    f"I/O call {target!r} in a non-boundary function reaches outside the "
                    "process off the boundary. Do the I/O at a boundary (@boundary / route "
                    "handler) and pass the result into the pure interior.",
                    node,
                )
            )
        return findings

    def check_p005():
        """HC-P005: a call to `isinstance` or `type` in a non-boundary function — a runtime
        type check that should be a vocabulary declared at the boundary (§5.5). Reported at
        the call's line."""
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is None or function.type != "identifier":
                continue
            if function.text.decode("utf-8") not in _TYPE_CHECK_CALLS:
                continue
            if not in_non_boundary_function(node):
                continue
            findings.append(
                diagnostic(
                    "HC-P005",
                    "warning",
                    "Runtime type check in business logic. Declare the constraint as a "
                    "vocabulary at the boundary instead.",
                    node,
                )
            )
        return findings

    def check_p006():
        """HC-P006: a cache decorator on a function that carries no profiling note — no
        evidence the cache was measured (§5.6). A profiling note is a `@profiled` decorator on
        the same function, or a `# honest: profiled` comment on the contiguous line(s)
        immediately above the construct. Reported at the cache decorator's line."""
        comment_lines = {}
        for node in nodes:
            if node.type != "comment":
                continue
            line, _col = line_col(node)
            raw = node.text.decode("utf-8") if node.text else ""
            comment_lines[line] = raw.lstrip("#").strip()

        def profiled_above(top_line):
            line = top_line - 1
            while line in comment_lines:
                if comment_lines[line] == "honest: profiled":
                    return True
                line -= 1
            return False

        findings = []
        for node in nodes:
            if node.type != "decorated_definition":
                continue
            decorators = [c for c in node.children if c.type == "decorator"]
            cache_decorators = [
                d for d in decorators if decorator_target(d) in _CACHE_DECORATORS
            ]
            if not cache_decorators:
                continue
            has_profiled_decorator = any(
                decorator_target(d) == "profiled" for d in decorators
            )
            top_line, _col = line_col(node)
            if has_profiled_decorator or profiled_above(top_line):
                continue
            findings.append(
                diagnostic(
                    "HC-P006",
                    "warning",
                    "Cache decorator without a profiling note. Add a @profiled decorator or "
                    "a '# honest: profiled' comment proving the cache was measured.",
                    cache_decorators[0],
                )
            )
        return findings

    # The per-file AST rules: each reads the shared `nodes` once-walked above and returns its
    # findings as data. check_source folds the tuple in one pass, so adding a per-file rule is
    # adding a row. HC-P003 (check_classes) is the first row. The construction-rule dispatch
    # below stays keyed by constructor name; this table is the structural-honesty rules.
    per_file_rules = (
        check_classes,
        check_p001,
        check_p007,
        check_p011,
        check_p016,
        check_p002,
        check_p004,
        check_p005,
        check_p006,
    )

    diagnostics = []
    for rule in per_file_rules:
        diagnostics.extend(rule())
    for node in nodes:
        if node.type != "call":
            continue
        canonical = canonical_name(node)
        if canonical not in construction_handlers:
            continue
        diagnostics.extend(construction_handlers[canonical](node))
    return diagnostics


def pair_source(path, text):
    """Join one discovered path with its already-read text into a SourceFile (§4.1).

    run_check calls this once per discovered file in crossing mode, after discover_files
    gave the path and read_source gave the text, to assemble the list<SourceFile> whole-
    package view cross_declaration takes. It reads nothing and decides nothing — it only
    joins the two values into the record the crossing core is fed.
    """
    return {"path": path, "text": text}


def cross_declaration(sources, declaration, export_source, rule_ids):
    """The pure core of the declaration-crossing path, the crossing-mode counterpart of
    check_source (sections 4.1, 4.2). It crosses one module's .hd declaration against the
    module's whole package of source files at once and returns the declaration-crossing
    findings as data, running only the crossing rules named in rule_ids — an empty list runs
    all five. It opens no file and executes no application code; read_declaration and
    read_source did the reads. It raises nothing: a disagreement comes back as a Diagnostic.

    The per-rule crossing logic is nested here as data, exactly as check_source holds the
    construction rules, never as a separately declared function.
    """
    declared = {fn["name"]: fn for fn in declaration["functions"]}

    def own_nodes(fdef):
        """The body descendants that belong to the function itself: the search does not
        descend into a nested def or lambda, whose statements are that inner scope's own, so
        a `return None` or a `yield` in a nested helper is not read as this function's
        (sections 4.2, §HC-R004, §HC-R005)."""
        body = fdef.child_by_field_name("body")
        found = []
        if body is None:
            return found

        def gather(node):
            for child in node.named_children:
                if child.type in _INNER_SCOPES:
                    continue
                found.append(child)
                gather(child)

        gather(body)
        return found

    def is_async(fdef):
        return any(child.type == "async" for child in fdef.children)

    def returns_nothing(fdef):
        """True when the function's own body has an explicit `return None` or a bare
        `return` — the two ways a Python function answers the host nothing outright
        (§HC-R004). A fall-off-the-end is not counted, matching the rule's own test."""
        for node in own_nodes(fdef):
            if node.type != "return_statement":
                continue
            children = node.named_children
            if not children:
                return True
            if children[0].type == "none":
                return True
        return False

    def body_yields(fdef):
        return any(node.type == "yield" for node in own_nodes(fdef))

    def arity(fdef):
        params = fdef.child_by_field_name("parameters")
        if params is None:
            return 0
        return sum(1 for child in params.named_children if child.type != "comment")

    def calls_of(fdef):
        """The names this function calls in its own body — a call whose function is a plain
        identifier (§HC-R002). A call inside a nested def belongs to that inner scope."""
        names = set()
        for node in own_nodes(fdef):
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is not None and function.type == "identifier":
                names.add(function.text.decode("utf-8"))
        return names

    def unwrap(top_node):
        """A top-level function and its decorator texts, or (None, []) for a non-function
        top-level node. A decorated def wraps the function_definition under `definition`."""
        if top_node.type == "function_definition":
            return top_node, []
        if top_node.type == "decorated_definition":
            definition = top_node.child_by_field_name("definition")
            if definition is not None and definition.type == "function_definition":
                decorators = [
                    child.text.decode("utf-8")
                    for child in top_node.children
                    if child.type == "decorator"
                ]
                return definition, decorators
        return None, []

    def facts_of(source_file):
        """The code facts of each top-level function in one source file: its name, location,
        async-ness, whether it can answer nothing, whether it yields, whether it is a context
        manager, its own call names and its parameter count. A file that does not parse
        contributes nothing — a parse failure is HC-SYN's finding, not this core's."""
        parsed = parse_source(source_file["text"].encode("utf-8"), source_file["path"])
        if "ok" not in parsed:
            return []
        facts = []
        for top_node in parsed["ok"].root_node.named_children:
            fdef, decorators = unwrap(top_node)
            if fdef is None:
                continue
            name_node = fdef.child_by_field_name("name")
            if name_node is None:
                continue
            line, col = line_col(fdef)
            facts.append(
                {
                    "name": name_node.text.decode("utf-8"),
                    "source_location": f"{source_file['path']}:{line}:{col}",
                    "is_async": is_async(fdef),
                    "returns_nothing": returns_nothing(fdef),
                    "yields": body_yields(fdef),
                    "is_context_manager": any(
                        "contextmanager" in decorator for decorator in decorators
                    ),
                    "calls": calls_of(fdef),
                    "arity": arity(fdef),
                }
            )
        return facts

    def literal_all(text):
        """The names a literal `__all__ = [...]` lists in the export source, or None when the
        source carries no literal __all__ to read — absent, or built by a call (§HC-REF005).
        An empty literal list is a declared surface of nothing, which is not None."""
        if not text:
            return None
        parsed = parse_source(text.encode("utf-8"), "exports.py")
        if "ok" not in parsed:
            return None
        for node in walk(parsed["ok"].root_node):
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if left.text.decode("utf-8") != "__all__":
                continue
            if right.type not in ("list", "tuple", "set"):
                return None
            return [
                ast.literal_eval(member.text.decode("utf-8"))
                for member in right.named_children
                if member.type == "string"
            ]
        return None

    code_functions = [fact for source in sources for fact in facts_of(source)]
    defined_names = {fact["name"] for fact in code_functions}

    def finding(rule_id, message, source_location):
        return {
            "rule_id": rule_id,
            "severity": "error",
            "message": message,
            "source_location": source_location,
            "context": "",
            "fixable": False,
        }

    def declared_absence(declaration_fn):
        return any(atom["name"] in _ABSENCE_ATOMS for atom in declaration_fn["ret"])

    def check_r002():
        """A declared boundary_out that calls, in the code, a function the declaration marks
        orchestrator or boundary_in — an output boundary invoking inward (§HC-R002). A callee
        the declaration does not name is skipped."""
        inward = frozenset({"orchestrator", "boundary_in"})
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or declaration_fn["role"] != "boundary_out":
                continue
            for callee in sorted(fact["calls"]):
                callee_fn = declared.get(callee)
                if callee_fn is None or callee_fn["role"] not in inward:
                    continue
                findings.append(
                    finding(
                        "HC-R002",
                        f"'{fact['name']}' is declared boundary_out and invokes '{callee}', "
                        f"declared {callee_fn['role']}. An output boundary is a terminus: "
                        "return a value the caller acts on, or move the work upstream of the "
                        "boundary.",
                        fact["source_location"],
                    )
                )
        return findings

    def check_r003():
        """A declared function whose code async-ness disagrees with its declared awaited
        (§HC-R003)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or fact["is_async"] == declaration_fn["awaited"]:
                continue
            findings.append(
                finding(
                    "HC-R003",
                    f"'{fact['name']}' is async def and its declaration does not say awaited."
                    if fact["is_async"]
                    else f"'{fact['name']}' is declared awaited and is a plain def.",
                    fact["source_location"],
                )
            )
        return findings

    def check_r004():
        """A declared function whose code can answer nothing while its card names no absence
        arm, or the reverse (§HC-R004). The default — absent means the card promises an
        answer — is verified against the code, not assumed (P15)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None:
                continue
            if fact["returns_nothing"] == declared_absence(declaration_fn):
                continue
            findings.append(
                finding(
                    "HC-R004",
                    f"'{fact['name']}' can return None and its card names no absence arm. "
                    "Add '| NOTHING' to the return, or stop returning None."
                    if fact["returns_nothing"]
                    else f"'{fact['name']}' is declared to return an absence and never "
                    "returns None. Remove the absence arm, or return None where the answer "
                    "is absent.",
                    fact["source_location"],
                )
            )
        return findings

    def check_r005():
        """A declared function whose body yields while its card returns a value, and which is
        not a context manager (§HC-R005)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or not fact["yields"] or fact["is_context_manager"]:
                continue
            findings.append(
                finding(
                    "HC-R005",
                    f"'{fact['name']}' is declared and its body yields, so it answers with a "
                    "stream rather than a value. Return a value, or move the laziness into a "
                    "helper this module does not declare.",
                    fact["source_location"],
                )
            )
        return findings

    def check_ref005():
        """The declared, defined and exported sets resolve to each other (§HC-REF005): an
        exported name the declaration does not name, a declared name defined nowhere, or a
        declared parameter count that disagrees. An absent or non-literal __all__ fails the
        rule rather than passing it."""
        module_root = sources[0]["path"] if sources else "exports.py"
        exported = literal_all(export_source)
        if exported is None:
            return [
                finding(
                    "HC-REF005",
                    "the module publishes no literal export list, so its surface is inferred "
                    "rather than declared and this rule cannot read it. Write the list.",
                    module_root,
                )
            ]
        declared_names = set(declared)
        location_of = {fact["name"]: fact["source_location"] for fact in code_functions}
        arity_of = {fact["name"]: fact["arity"] for fact in code_functions}
        findings = []
        for name in sorted(set(exported) - declared_names):
            findings.append(
                finding(
                    "HC-REF005",
                    f"'{name}' is exported by the module and declared in no .hd. Declare it, "
                    "or stop exporting it.",
                    location_of.get(name, module_root),
                )
            )
        for name in sorted(declared_names - defined_names):
            findings.append(
                finding(
                    "HC-REF005",
                    f"'{name}' is declared and defined nowhere. Implement it, or remove the "
                    "declaration.",
                    module_root,
                )
            )
        for name in sorted(declared_names & defined_names):
            declared_arity = len(declared[name]["params"])
            if arity_of[name] != declared_arity:
                findings.append(
                    finding(
                        "HC-REF005",
                        f"'{name}' is declared with {declared_arity} parameters and defined "
                        f"with {arity_of[name]}.",
                        location_of[name],
                    )
                )
        return findings

    # The crossing dispatch: each selected crossing rule runs once over the whole package.
    # rule_ids is narrowed to CrossingRule members (an empty list runs all five); a rule id
    # the table does not name is not a crossing rule and is skipped, guarded by membership.
    crossing_rules = {
        "HC-R002": check_r002,
        "HC-R003": check_r003,
        "HC-R004": check_r004,
        "HC-R005": check_r005,
        "HC-REF005": check_ref005,
    }
    selected = rule_ids if rule_ids else list(crossing_rules)
    findings = []
    for rule_id in selected:
        if rule_id not in crossing_rules:
            continue
        findings.extend(crossing_rules[rule_id]())
    return findings
