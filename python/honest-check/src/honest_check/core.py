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
import fnmatch
import itertools

from honest_parse import language_of, line_col, parse, parse_source, walk

from honest_check.watchlists import IO_WATCH_LIST, NONDETERMINISTIC_WATCH_LIST

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

# The Python HTTP-response markers HC-P017 names (§HC-P017). A function whose own body calls
# one of these produces HTTP output, so it must be a declared @link whose emits vocabulary is
# declared, or it escapes chain-contract testing of its serialized output. These are the
# response constructors and the template call `render`, matched by the call's name
# (called_name). They are not the watchlists.py I/O set, which this rule does not read.
_HTTP_RESPONSE_MARKERS = frozenset(
    {
        "Response",
        "JSONResponse",
        "HTMLResponse",
        "PlainTextResponse",
        "RedirectResponse",
        "FileResponse",
        "StreamingResponse",
        "render",
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

# The builtins whose empty call stands for absence, not a baked-in value (§HC-P015). A
# `list()`/`dict()`/`set()`/`tuple()`/`frozenset()` with no argument is the honest empty
# default; the same name called with an argument is a real value and fires.
_EMPTY_CONSTRUCTORS = frozenset({"list", "dict", "set", "tuple", "frozenset"})

# The three verbs a `# honest: <verb> ...` directive may name (§7.1). `ignore` suppresses a
# finding on its own line, `disable` opens a range a matching `enable` closes, and `enable`
# only closes a range. A comment whose first word after `honest:` is none of these is not a
# directive and is left alone, the common case for an ordinary `# honest: profiled` note.
_SUPPRESSION_KEYWORDS = frozenset({"ignore", "disable", "enable"})

# The grammars honest-parse detects for a template file (§HC-REF002). Both read `{% %}`
# tags under the jinja grammar and class attributes under the html grammar; which one a
# file's extension maps to only decides it is a template, not how its references are read.
_TEMPLATE_GRAMMARS = frozenset({"html", "jinja"})

# The classList methods whose string-literal arguments name a class (§HC-REF003). A call
# `el.classList.<method>(...)` where method is one of these contributes each string argument
# as a class token; a non-literal argument carries no literal to resolve and is skipped.
_CLASSLIST_METHODS = frozenset({"add", "remove", "toggle", "replace", "contains"})

# The interpolation markers a class value carries when it is dynamic (§HC-REF003). A class
# attribute value or template carrying any of these is variable, not a fixed set of tokens,
# so it is skipped whole — the stated bound of the class check, not an oversight.
_INTERPOLATION_MARKERS = ("{{", "}}", "{%", "%}")


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
        """The base-type map of a vocabulary's first argument: name -> (kind, payload).
        kind is 'set' with a frozenset of members, or 'predicate' with the recognizer's value
        node (a lambda or any other opaque recognizer honest-check cannot run). HC009 reads
        that node for a risky operation; HC003 and HC011 read only the kind."""
        base_types = {}
        for pair in dictionary_node.named_children:
            if pair.type != "pair":
                continue
            name = literal_string(pair.child_by_field_name("key"))
            value = pair.child_by_field_name("value")
            if value.type == "set":
                base_types[name] = ("set", frozenset(string_members(value)))
            else:
                base_types[name] = ("predicate", value)
        return base_types

    def predicate_is_risky(value):
        """True when a predicate's expression holds a node that throws on a non-matching
        input (§HC009): a call to bare `int` or `float`, a subscript access, or a `/` or `//`
        division. A predicate that throws is a recognizer that rejects by exception rather
        than by returning False."""
        for node in walk(value):
            if node.type == "call":
                function = node.child_by_field_name("function")
                if (
                    function is not None
                    and function.type == "identifier"
                    and function.text.decode("utf-8") in ("int", "float")
                ):
                    return True
            elif node.type == "subscript":
                return True
            elif node.type == "binary_operator" and any(
                child.type in ("/", "//") for child in node.children
            ):
                return True
        return False

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

        for name, (kind, payload) in base_types.items():
            if kind != "predicate":
                continue
            if payload is not None and predicate_is_risky(payload):
                findings.append(
                    diagnostic(
                        "HC009",
                        "warning",
                        f"Predicate recognizer {name!r} may throw on non-matching input. "
                        "Wrap in try/except or guard with isinstance() — verified by "
                        "honest-test.",
                        call_node,
                    )
                )
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
        vocabulary; HC-SM03/04: an unreachable or dead state (section 4.1)."""
        findings = []
        positionals, keywords = call_arguments(call_node)
        if len(positionals) < 4:
            return findings
        states = string_members(positionals[0])
        state_set = set(states)
        events = set(string_members(positionals[1]))
        transitions = positionals[2]
        initial = literal_string(positionals[3]) if positionals[3].type == "string" else None
        terminal_node = keywords.get("terminal")
        if terminal_node is None and len(positionals) >= 5:
            terminal_node = positionals[4]
        terminal = set(string_members(terminal_node)) if terminal_node is not None else set()

        transition_pairs = []
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
            value = pair.child_by_field_name("value")
            target = literal_string(value) if value is not None and value.type == "string" else None
            transition_pairs.append((state, event, target))
            if state not in state_set:
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
        if initial is not None and initial not in state_set:
            findings.append(
                diagnostic(
                    "HC-SM05",
                    "error",
                    f"Initial state {initial!r} not in states vocabulary",
                    call_node,
                )
            )

        # HC-SM03: a declared state the forward walk from the initial state never reaches,
        # and that is not itself the initial state, is unreachable. The walk is a plain set
        # closure over the transition edges.
        if initial is not None:
            reachable = {initial}
            frontier = {initial}
            while frontier:
                nxt = set()
                for state, _event, target in transition_pairs:
                    if state in frontier and target is not None and target not in reachable:
                        reachable.add(target)
                        nxt.add(target)
                frontier = nxt
            for state in states:
                if state not in reachable and state != initial:
                    findings.append(
                        diagnostic(
                            "HC-SM03",
                            "warning",
                            f"State {state!r} is unreachable",
                            call_node,
                        )
                    )

        # HC-SM04: a declared state with no outgoing transition that is not declared terminal
        # is a dead state.
        states_with_outgoing = {state for state, _event, _target in transition_pairs}
        for state in states:
            if state not in states_with_outgoing and state not in terminal:
                findings.append(
                    diagnostic(
                        "HC-SM04",
                        "warning",
                        f"State {state!r} has no outgoing transitions and is not "
                        "declared terminal",
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

    def is_empty_default(value):
        """True when a parameter's default stands for absence rather than a baked-in value
        (§HC-P015): None, False, a zero number, an empty string, an empty list/dict/tuple
        literal, or an empty-constructor call. A populated literal, a non-zero number, a
        non-empty string, True, a name or any other call is a real value and is not empty."""
        kind = value.type
        if kind in ("none", "false"):
            return True
        if kind in ("integer", "float"):
            return ast.literal_eval(value.text.decode("utf-8")) == 0
        if kind == "string":
            return not any(
                child.type in ("string_content", "interpolation")
                for child in value.named_children
            )
        if kind in ("list", "dictionary", "tuple"):
            return len(value.named_children) == 0
        if kind == "call":
            function = value.child_by_field_name("function")
            if function is None or function.type != "identifier":
                return False
            if function.text.decode("utf-8") not in _EMPTY_CONSTRUCTORS:
                return False
            positionals, keywords = call_arguments(value)
            return not positionals and not keywords
        return False

    def check_p015():
        """HC-P015: a parameter whose default value is a real, non-empty value (§HC-P015). A
        real-valued default absorbs the caller's omission and leaves the omitted-argument path
        untested. Reported at the parameter's line; an empty default (the honest nothing) does
        not fire."""
        findings = []
        for node in nodes:
            if node.type not in ("default_parameter", "typed_default_parameter"):
                continue
            value = node.child_by_field_name("value")
            if value is None or is_empty_default(value):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<parameter>"
            findings.append(
                diagnostic(
                    "HC-P015",
                    "warning",
                    f"Parameter {name!r} defaults to a real value. A default hides whether "
                    "the caller chose the value or omitted it, and leaves the omitted-argument "
                    "path untested. Make the parameter required, or default it to empty if "
                    "absence is the honest nothing.",
                    node,
                )
            )
        return findings

    def is_immutable_value(value):
        """True when a module-level binding's right side is provably immutable (§5.4, §872):
        a number, a string, a bool, None, a tuple literal, a negated immutable, or a
        `frozenset(...)` call. Everything else — a list, dict or set literal, a comprehension,
        a name, any other call — is mutable or not provably immutable, so a read of it fires
        HC008."""
        kind = value.type
        if kind in (
            "integer",
            "float",
            "string",
            "concatenated_string",
            "true",
            "false",
            "none",
            "tuple",
        ):
            return True
        if kind == "unary_operator":
            operand = value.child_by_field_name("argument")
            return operand is not None and is_immutable_value(operand)
        if kind == "call":
            function = value.child_by_field_name("function")
            return (
                function is not None
                and function.type == "identifier"
                and function.text.decode("utf-8") == "frozenset"
            )
        return False

    def module_mutable_globals():
        """The module-level names bound to a mutable (or not provably immutable) value — the
        globals a read of which makes a link impure (§5.4, §872). A name bound to an immutable
        value, and an imported or def/class name (never an assignment target), are not here."""
        names = set()
        for top in root.named_children:
            node = top
            if top.type == "expression_statement" and top.named_children:
                node = top.named_children[0]
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if not is_immutable_value(right):
                names.add(left.text.decode("utf-8"))
        return names

    def param_names(param):
        """The names a single parameter node binds — a bare identifier, or the `name` of a
        typed or defaulted parameter. A splat or other shape binds nothing here."""
        if param.type == "identifier":
            return {param.text.decode("utf-8")}
        name = param.child_by_field_name("name")
        if name is not None and name.type == "identifier":
            return {name.text.decode("utf-8")}
        return set()

    def link_locals(fdef, body):
        """The names local to a link — its parameters plus the names it assigns in its own
        body. A read of one of these is not a read of a module global (§5.4)."""
        names = set()
        params = fdef.child_by_field_name("parameters")
        if params is not None:
            for child in params.named_children:
                names |= param_names(child)
        for node in body:
            if node.type in ("assignment", "augmented_assignment"):
                target = node.child_by_field_name("left")
                if target is not None and target.type == "identifier":
                    names.add(target.text.decode("utf-8"))
        return names

    def is_attribute_suffix(node):
        """True when an identifier is the attribute part of an `x.name` access — the `.name`,
        not a read of `name` itself. Reading `config.timeout` reads `config`, not a global
        called `timeout` (§5.4)."""
        parent = node.parent
        return (
            parent is not None
            and parent.type == "attribute"
            and parent.child_by_field_name("attribute") is node
        )

    def is_keyword_name(node):
        """True when an identifier is a keyword argument's name — the `k` in `f(k=v)`, which
        names a parameter of the callee, not a global read (§5.4)."""
        parent = node.parent
        return (
            parent is not None
            and parent.type == "keyword_argument"
            and parent.child_by_field_name("name") is node
        )

    def watched(target, watch):
        """True when a call's dotted target is on a watch list: an exact entry matches by
        equality, and an entry carrying a `*` matches as a glob — a trailing `.*` names any
        attribute of a module, a trailing `*` is a prefix, a `*` between dots is one segment
        (§HC008)."""
        for entry in watch:
            if "*" in entry:
                if fnmatch.fnmatchcase(target, entry):
                    return True
            elif target == entry:
                return True
        return False

    def link_is_impure(fdef, watch, mutable_globals):
        """True when a link's own body calls a watched function or reads a module-level
        mutable global (§HC008). The body search does not descend into a nested def or
        lambda, whose statements are that inner scope's own."""
        body = own_body(fdef)
        locals_bound = link_locals(fdef, body)
        for node in body:
            if node.type == "call":
                target = dotted_target(node)
                if target is not None and watched(target, watch):
                    return True
            elif node.type == "identifier":
                name = node.text.decode("utf-8")
                if (
                    name in mutable_globals
                    and name not in locals_bound
                    and not is_attribute_suffix(node)
                    and not is_keyword_name(node)
                ):
                    return True
        return False

    def is_link_decorated(fdef):
        """True when a function carries a `@link` decorator, bare or called — the chain-link
        declaration HC008 and HC001 both read for a declared link (§HC008, §4.2)."""
        return any(decorator_target(d) == "link" for d in decorators_of(fdef))

    def check_hc008():
        """HC008: a non-boundary `@link` whose body calls a function on the impurity watch
        list for the file's language, or reads a module-level mutable global (§HC008). A
        `@link(boundary=True)` or `@boundary` link is exempt. Reported once, at the link's
        `def` line. The watch lists are keyed by the language honest-parse detected for this
        path; a language with no published list has an empty watch, so the call clause is
        inert for it."""
        language = language_of(path).get("ok")
        io = IO_WATCH_LIST[language] if language in IO_WATCH_LIST else frozenset()
        nondeterministic = (
            NONDETERMINISTIC_WATCH_LIST[language]
            if language in NONDETERMINISTIC_WATCH_LIST
            else frozenset()
        )
        watch = io | nondeterministic
        mutable_globals = module_mutable_globals()
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            if not is_link_decorated(node):
                continue
            if any(is_boundary_decorator(d) for d in decorators_of(node)):
                continue
            if not link_is_impure(node, watch, mutable_globals):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<link>"
            findings.append(
                diagnostic(
                    "HC008",
                    "warning",
                    f"Link {name!r} may be impure: it calls a watched function or reads "
                    "module-level mutable state. Add boundary=True if the I/O is intentional.",
                    node,
                )
            )
        return findings

    def local_function_links():
        """Each function defined in this file, mapped to whether it carries a `@link`
        decorator (§4.2, HC001). A chain positional that resolves to one of these names is a
        local link declaration honest-check can read; a name not here is defined elsewhere, so
        its declaration is invisible to honest-check and the positional is left alone."""
        links = {}
        for node in nodes:
            if node.type != "function_definition":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            links[name_node.text.decode("utf-8")] = is_link_decorated(node)
        return links

    def check_hc001():
        """HC001: a `chain()` link that resolves to a locally-defined function carrying no
        `@link` declaration, so its vocabulary is undeclared and the chain cannot be
        contract-tested (§4.2). Reported at the `chain()` call's line. A positional that
        resolves to no local function — an import or an expression — is skipped: honest-check
        cannot see its declaration, and a miss is preferred to a false positive here."""
        links = local_function_links()
        findings = []
        for node in nodes:
            if node.type != "call" or canonical_name(node) != "chain":
                continue
            positionals, _keywords = call_arguments(node)
            for argument in positionals:
                if argument.type != "identifier":
                    continue
                name = argument.text.decode("utf-8")
                if name not in links or links[name]:
                    continue
                findings.append(
                    diagnostic(
                        "HC001",
                        "error",
                        f"Chain link {name!r} has no vocabulary declared. Wrap it with "
                        "@link(accepts=..., emits=...) or the link() constructor.",
                        node,
                    )
                )
        return findings

    def is_orchestrator(fdef):
        """True when a function carries an `@orchestrator` decorator, bare or called — matched
        by decorator name the same way a boundary decorator is (§4.2, HC-OR001)."""
        return any(decorator_target(d) == "orchestrator" for d in decorators_of(fdef))

    def check_hc_or001():
        """HC-OR001: a declared orchestrator whose own body calls another function the file
        declares an orchestrator — orchestrator composition, the invisible nesting the
        architecture forbids (§4.2). Reported at the calling site's line. The body walk is the
        orchestrator's own, not a nested scope's."""
        orchestrators = []
        names = set()
        for node in nodes:
            if node.type != "function_definition" or not is_orchestrator(node):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<orchestrator>"
            orchestrators.append((node, name))
            names.add(name)
        findings = []
        for fdef, name in orchestrators:
            for statement in own_body(fdef):
                if statement.type != "call":
                    continue
                callee = called_name(statement)
                if callee not in names:
                    continue
                findings.append(
                    diagnostic(
                        "HC-OR001",
                        "error",
                        f"Orchestrator {name!r} calls orchestrator {callee!r}. "
                        "Orchestrators are the root of an operation and do not compose. "
                        "Extract the shared logic as a pure helper (if no I/O) or as a chain "
                        "(if I/O is involved).",
                        statement,
                    )
                )
        return findings

    def link_declares_emits(fdef):
        """True when a function carries a `@link` decorator that passes an `emits` keyword — the
        emits vocabulary HC-P017 requires of an HTTP-producing link (§HC-P017). Read the same
        way is_boundary_decorator reads `boundary`: from the decorator call's keyword
        arguments. A bare `@link` with no call declares no emits."""
        for decorator in decorators_of(fdef):
            if decorator_target(decorator) != "link":
                continue
            expr = decorator_expression(decorator)
            if expr is None or expr.type != "call":
                continue
            _positionals, keywords = call_arguments(expr)
            if "emits" in keywords:
                return True
        return False

    def check_p017():
        """HC-P017: a function whose own body calls an HTTP-response marker produces HTTP output
        (§HC-P017). It fires unless the function is a `@link` whose `emits` vocabulary is
        declared, because otherwise its serialized output is classified by no vocabulary and
        escapes chain-contract testing. Reported at the function's `def` line."""
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            produces_http = any(
                called_name(child) in _HTTP_RESPONSE_MARKERS
                for child in own_body(node)
                if child.type == "call"
            )
            if not produces_http:
                continue
            if is_link_decorated(node) and link_declares_emits(node):
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<function>"
            findings.append(
                diagnostic(
                    "HC-P017",
                    "error",
                    f"Function {name!r} produces HTTP output without being a declared @link "
                    "with an emits vocabulary. Declare emits covering status, content-type, "
                    "body shape, headers, and cookies, or delegate to a declared serializer "
                    "link.",
                    node,
                )
            )
        return findings

    def construction_maps():
        """Each file-local variable bound to a `vocabulary(...)` or a `binding(...)` call,
        mapped to that construction call node (§HC004, §HC005). A name bound to anything else
        is not here; a name honest-check cannot resolve to one of these two constructions is
        one it cannot cross, and a pairing site naming it is left alone."""
        vocab_calls = {}
        binding_calls = {}
        for node in nodes:
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if right.type != "call":
                continue
            canonical = canonical_name(right)
            name = left.text.decode("utf-8")
            if canonical == "vocabulary":
                vocab_calls[name] = right
            elif canonical == "binding":
                binding_calls[name] = right
        return vocab_calls, binding_calls

    def vocabulary_types(vocab_call):
        """The type surface of a `vocabulary(...)` call: its base-type names, its composed-type
        names, the base names its composed types require, and the base names its composed types
        capture (§HC004, §HC005). base_types_of reads the first-argument dictionary's keys; the
        composed data is read from each `composed(name, requires, captures)` call in the
        `composed_types` keyword, the same shape check_composed reads."""
        positionals, keywords = call_arguments(vocab_call)
        base_names = set()
        if positionals and positionals[0].type == "dictionary":
            base_names = set(base_types_of(positionals[0]))
        composed_names = set()
        composed_requires = set()
        composed_captures = set()
        composed_list = keywords.get("composed_types")
        if composed_list is not None:
            for child in composed_list.named_children:
                if child.type != "call" or canonical_name(child) != "composed":
                    continue
                c_positionals, _c_keywords = call_arguments(child)
                if c_positionals and c_positionals[0].type == "string":
                    composed_names.add(literal_string(c_positionals[0]))
                if len(c_positionals) >= 2 and c_positionals[1].type == "dictionary":
                    for pair in c_positionals[1].named_children:
                        if pair.type == "pair":
                            composed_requires.add(
                                literal_string(pair.child_by_field_name("key"))
                            )
                if len(c_positionals) >= 3 and c_positionals[2].type == "string":
                    composed_captures.add(literal_string(c_positionals[2]))
        return base_names, composed_names, composed_requires, composed_captures

    def binding_keys(binding_call):
        """The type names a `binding(...)` call binds — the keys of its first-argument table
        (§HC004, §HC005)."""
        positionals, _keywords = call_arguments(binding_call)
        if not positionals or positionals[0].type != "dictionary":
            return set()
        keys = set()
        for pair in positionals[0].named_children:
            if pair.type == "pair":
                keys.add(literal_string(pair.child_by_field_name("key")))
        return keys

    def vocabulary_binding_pairs():
        """Each (vocabulary calls, binding call) a classify or link pairs by name (§HC004,
        §HC005). A `classify(tokens, vocab, bind=b)` pairs positional 2 with the `bind`
        keyword, and its vocabulary list is the one vocab. A `link(accepts=v, emits=e, binds=b)`
        (bare or as a decorator) pairs `accepts` with `binds`, and its binding legitimately
        spans both the types it accepts and the types it emits, so its vocabulary list is
        `accepts` followed by `emits` when `emits` resolves — the binding is crossed against the
        union of both. A link with no `emits` keyword, or an `emits` that resolves to no local
        vocabulary, lists `accepts` alone, so it behaves as the union with the empty set. A site
        with no binding keyword uses the identity auto_binding, which binds each type to itself,
        so neither rule fires and the site is not a pair. A vocabulary or binding argument that
        is not a plain name, or a name that resolves to no local construction, is skipped —
        honest-check cannot cross what it was not handed. A pair reached from two sites is
        crossed once."""
        vocab_calls, binding_calls = construction_maps()
        pairs = []
        seen = set()
        for node in nodes:
            if node.type != "call":
                continue
            canonical = canonical_name(node)
            positionals, keywords = call_arguments(node)
            if canonical == "classify":
                vocab_arg = positionals[1] if len(positionals) >= 2 else None
                emits_arg = None
                binding_arg = keywords.get("bind")
            elif canonical == "link":
                vocab_arg = keywords.get("accepts")
                emits_arg = keywords.get("emits")
                binding_arg = keywords.get("binds")
            else:
                continue
            if binding_arg is None:
                continue
            if (
                vocab_arg is None
                or vocab_arg.type != "identifier"
                or binding_arg.type != "identifier"
            ):
                continue
            vocab_call = vocab_calls.get(vocab_arg.text.decode("utf-8"))
            binding_call = binding_calls.get(binding_arg.text.decode("utf-8"))
            if vocab_call is None or binding_call is None:
                continue
            resolved = [vocab_call]
            if emits_arg is not None and emits_arg.type == "identifier":
                emits_call = vocab_calls.get(emits_arg.text.decode("utf-8"))
                if emits_call is not None:
                    resolved.append(emits_call)
            key = (tuple(id(call) for call in resolved), id(binding_call))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((resolved, binding_call))
        return pairs

    def check_hc004():
        """HC004: a vocabulary base type the paired binding never binds and no composed type
        uses, in its requires or as its captures, is dead (§HC004). Reported at the
        vocabulary() call that declares the dead type, once per dead type. A link crosses the
        binding against the union of its accepts and emits vocabularies, so a composed type in
        either rescues a base type in either. A classify with no bind, or a link with no binds,
        pairs the identity auto_binding and does not fire."""
        findings = []
        for vocab_calls, binding_call in vocabulary_binding_pairs():
            bound = binding_keys(binding_call)
            composed_requires = set()
            composed_captures = set()
            per_vocab_bases = []
            for vocab_call in vocab_calls:
                base_names, _composed_names, requires, captures = vocabulary_types(vocab_call)
                per_vocab_bases.append((vocab_call, base_names))
                composed_requires |= requires
                composed_captures |= captures
            for vocab_call, base_names in per_vocab_bases:
                for type_name in sorted(base_names):
                    if type_name in bound:
                        continue
                    if type_name in composed_requires or type_name in composed_captures:
                        continue
                    findings.append(
                        diagnostic(
                            "HC004",
                            "warning",
                            f"Type {type_name!r} is declared in the vocabulary but no binding "
                            "slot or composed type uses it. Bind it to a slot, use it in a "
                            "composed type, or remove it from the vocabulary.",
                            vocab_call,
                        )
                    )
        return findings

    def check_hc005():
        """HC005: a binding key that names neither a base type nor a composed type of the
        paired vocabulary binds a type no token can carry (§HC005). Reported at the binding()
        call's line, once per unmatched key. A link crosses the binding against the union of its
        accepts and emits vocabularies, so an emit-type binding entry is bound, not unmatched. A
        classify with no bind, or a link with no binds, pairs the identity auto_binding and does
        not fire."""
        findings = []
        for vocab_calls, binding_call in vocabulary_binding_pairs():
            known = set()
            for vocab_call in vocab_calls:
                base_names, composed_names, _requires, _captures = vocabulary_types(vocab_call)
                known |= base_names | composed_names
            for type_name in sorted(binding_keys(binding_call)):
                if type_name in known:
                    continue
                findings.append(
                    diagnostic(
                        "HC005",
                        "warning",
                        f"Binding references type {type_name!r} not found in the paired "
                        "vocabulary, so no classified token can reach its slot. Add the type "
                        "to the vocabulary, or remove the binding entry.",
                        binding_call,
                    )
                )
        return findings

    def check_hc010():
        """HC010: a declared @link whose emits vocabulary names a type its body never produces
        (§"Declared emission never produced"). For a `@link(accepts=A, emits=E, binds=B)`, a
        type E names, that the body never writes to the manifest and A does not already carry,
        is a phantom emission: the link promises to produce it and does not. The body produces a
        type by writing the manifest slot that type binds to — a subscript assignment
        `<p>["slot"] = ...` on the link's first parameter `<p>`, read back through B's
        slot-to-type inverse. Reported once at the link's def line, naming the phantom types. A
        link whose emits or binds argument is not a plain name, or resolves to no local
        construction, is skipped — honest-check cannot cross what it was not handed."""
        vocab_calls, binding_calls = construction_maps()
        findings = []
        for node in nodes:
            if node.type != "function_definition":
                continue
            link_call = None
            for decorator in decorators_of(node):
                if decorator_target(decorator) != "link":
                    continue
                expr = decorator_expression(decorator)
                if expr is not None and expr.type == "call":
                    link_call = expr
                break
            if link_call is None:
                continue
            _positionals, keywords = call_arguments(link_call)
            emits_arg = keywords.get("emits")
            binds_arg = keywords.get("binds")
            accepts_arg = keywords.get("accepts")
            if (
                emits_arg is None
                or emits_arg.type != "identifier"
                or binds_arg is None
                or binds_arg.type != "identifier"
            ):
                continue
            emits_call = vocab_calls.get(emits_arg.text.decode("utf-8"))
            binding_call = binding_calls.get(binds_arg.text.decode("utf-8"))
            if emits_call is None or binding_call is None:
                continue
            emitted_types, _emits_composed, _requires, _captures = vocabulary_types(emits_call)
            accepts_types = set()
            if accepts_arg is not None and accepts_arg.type == "identifier":
                accepts_call = vocab_calls.get(accepts_arg.text.decode("utf-8"))
                if accepts_call is not None:
                    accepts_types, _a_composed, _ar, _ac = vocabulary_types(accepts_call)
            binding_reverse = {}
            b_positionals, _b_keywords = call_arguments(binding_call)
            if b_positionals and b_positionals[0].type == "dictionary":
                for pair in b_positionals[0].named_children:
                    if pair.type != "pair":
                        continue
                    slot_value = pair.child_by_field_name("value")
                    if slot_value is not None and slot_value.type == "string":
                        binding_reverse[literal_string(slot_value)] = literal_string(
                            pair.child_by_field_name("key")
                        )
            first_param = None
            params = node.child_by_field_name("parameters")
            if params is not None:
                for child in params.named_children:
                    if child.type == "comment":
                        continue
                    names = param_names(child)
                    if names:
                        first_param = next(iter(names))
                    break
            produced_keys = set()
            if first_param is not None:
                for statement in own_body(node):
                    if statement.type != "assignment":
                        continue
                    target = statement.child_by_field_name("left")
                    if target is None or target.type != "subscript":
                        continue
                    obj = target.child_by_field_name("value")
                    index = target.child_by_field_name("subscript")
                    if obj is None or obj.type != "identifier":
                        continue
                    if obj.text.decode("utf-8") != first_param:
                        continue
                    if index is None or index.type != "string":
                        continue
                    produced_keys.add(literal_string(index))
            produced_types = {
                binding_reverse[key] for key in produced_keys if key in binding_reverse
            }
            phantom = emitted_types - produced_types - accepts_types
            if not phantom:
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<link>"
            findings.append(
                diagnostic(
                    "HC010",
                    "warning",
                    f"Link {name!r} declares it emits {sorted(phantom)} but its body never "
                    "produces them: it writes no manifest slot bound to the type and does not "
                    "accept the type. Write the slot, drop the type from emits, or accept it.",
                    node,
                )
            )
        return findings

    def check_hc002():
        """HC002: a chain seam whose adjacent links disagree on type — a link that accepts a
        type the previous link does not emit, so the chain cannot be contract-tested at that
        seam (§"Chain type mismatch"). For each chain() call, its positional links resolve in
        order to their local @link definitions; for each adjacent pair (link i-1, link i) from
        i=1, the types link i accepts that link i-1 does not emit are missing, and a non-empty
        missing set fires once at the chain() call's line, naming link i and the missing types.
        A positional that resolves to no local @link is skipped, so neither pair touching it
        fires — HC001 already reports an undeclared chain link. A keyword may name a single
        vocabulary or a `|` union of vocabularies; a union resolves to the union of the named
        vocabularies' base-type names (the same emits resolution HC010 reads). The first link's
        accepts is left unchecked here: its input is the derived boundary vocabulary (spec
        §497, the route-map/template derivation), which needs cross-artifact inputs honest-check
        does not ingest yet."""
        vocab_calls, _binding_calls = construction_maps()

        def vocab_arg_type_names(arg):
            """The base-type names a link's accepts or emits keyword value names (§HC002). A
            plain identifier resolves through vocab_calls to its vocabulary's base-type names; a
            `|` union of vocabularies resolves to the union of each operand's names; an operand
            naming no local vocabulary contributes nothing. A value of any other shape names no
            type here."""
            if arg is None:
                return set()
            if arg.type == "identifier":
                vocab_call = vocab_calls.get(arg.text.decode("utf-8"))
                if vocab_call is None:
                    return set()
                base_names, _composed, _requires, _captures = vocabulary_types(vocab_call)
                return base_names
            if arg.type == "binary_operator":
                return vocab_arg_type_names(
                    arg.child_by_field_name("left")
                ) | vocab_arg_type_names(arg.child_by_field_name("right"))
            return set()

        def link_call_of(fdef):
            """The `@link(...)` call node decorating a function, or None when its @link is bare
            or absent — the decorator call HC002 reads accepts and emits from."""
            for decorator in decorators_of(fdef):
                if decorator_target(decorator) != "link":
                    continue
                expr = decorator_expression(decorator)
                return expr if expr is not None and expr.type == "call" else None
            return None

        def seam_types(fdef, keyword):
            """The base-type names a link's @link decorator declares for one keyword (accepts
            or emits), or the empty set when the link declares none honest-check can resolve."""
            link_call = link_call_of(fdef)
            if link_call is None:
                return set()
            _positionals, keywords = call_arguments(link_call)
            return vocab_arg_type_names(keywords.get(keyword))

        link_defs = {}
        for node in nodes:
            if node.type != "function_definition":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None or not is_link_decorated(node):
                continue
            link_defs[name_node.text.decode("utf-8")] = node

        findings = []
        for node in nodes:
            if node.type != "call" or canonical_name(node) != "chain":
                continue
            positionals, _keywords = call_arguments(node)
            resolved = [
                link_defs.get(argument.text.decode("utf-8"))
                if argument.type == "identifier"
                else None
                for argument in positionals
            ]
            for i in range(1, len(resolved)):
                previous, current = resolved[i - 1], resolved[i]
                if previous is None or current is None:
                    continue
                missing = seam_types(current, "accepts") - seam_types(previous, "emits")
                if not missing:
                    continue
                name_node = current.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "<link>"
                findings.append(
                    diagnostic(
                        "HC002",
                        "error",
                        f"Chain link {name!r} accepts types the previous link does not emit: "
                        f"{sorted(missing)}. Change this link's accepts, change the previous "
                        "link's emits, or insert a link between them that produces the types.",
                        node,
                    )
                )
        return findings

    def features_vocabulary():
        """The feature-flag vocabulary this module declares: each flag name mapped to the set
        of states its `FEATURES[flag]["states"]` set names (§7, HC-HF001/HC-HF002). Read only
        from a module-scope `FEATURES = {...}` dict literal — the same top-level-assignment
        walk module_mutable_globals uses. Absent such a literal, an empty map, so both
        feature-flag rules have nothing to verify against and fire nothing (the spec's 'IF
        features is empty: RETURN')."""
        for top in root.named_children:
            node = top
            if top.type == "expression_statement" and top.named_children:
                node = top.named_children[0]
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if left.text.decode("utf-8") != "FEATURES" or right.type != "dictionary":
                continue
            features = {}
            for pair in right.named_children:
                if pair.type != "pair":
                    continue
                key = pair.child_by_field_name("key")
                if key is None or key.type != "string":
                    continue
                value = pair.child_by_field_name("value")
                states = set()
                if value is not None and value.type == "dictionary":
                    for inner in value.named_children:
                        if inner.type != "pair":
                            continue
                        inner_key = inner.child_by_field_name("key")
                        if inner_key is None or inner_key.type != "string":
                            continue
                        if literal_string(inner_key) != "states":
                            continue
                        inner_value = inner.child_by_field_name("value")
                        if inner_value is not None and inner_value.type == "set":
                            states = set(string_members(inner_value))
                features[literal_string(key)] = states
            return features
        return {}

    def feature_state_flag(call_node):
        """The flag a `feature_state(state, "flag")` call names — its second positional, a
        string literal — or None when the call names fewer than two positionals or a dynamic
        (non-literal) flag (§7). The call is resolved by name through called_name."""
        if called_name(call_node) != "feature_state":
            return None
        positionals, _keywords = call_arguments(call_node)
        if len(positionals) < 2 or positionals[1].type != "string":
            return None
        return literal_string(positionals[1])

    def module_dict_literals():
        """Each module-scope name bound to a dict literal, mapped to the set of string keys the
        literal declares (§7, HC-HF002). A name bound to anything but a module-scope dict
        literal is not here, so a handler table that resolves to no such name is skipped."""
        tables = {}
        for top in root.named_children:
            node = top
            if top.type == "expression_statement" and top.named_children:
                node = top.named_children[0]
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if right.type != "dictionary":
                continue
            keys = set()
            for pair in right.named_children:
                if pair.type != "pair":
                    continue
                key = pair.child_by_field_name("key")
                if key is not None and key.type == "string":
                    keys.add(literal_string(key))
            tables[left.text.decode("utf-8")] = keys
        return tables

    def check_hf001():
        """HC-HF001: a `feature_state(state, "flag")` call whose flag is not a key of the
        module's FEATURES vocabulary — an undeclared flag that raises KeyError at runtime (§7).
        Reported at the call's line. When FEATURES is not a readable module-scope dict literal
        the vocabulary is empty and the rule fires nothing."""
        features = features_vocabulary()
        if not features:
            return []
        findings = []
        for node in nodes:
            if node.type != "call":
                continue
            flag = feature_state_flag(node)
            if flag is None or flag in features:
                continue
            findings.append(
                diagnostic(
                    "HC-HF001",
                    "error",
                    f"feature_state references {flag!r}, which is not a declared flag in "
                    "FEATURES.",
                    node,
                )
            )
        return findings

    def check_hf002():
        """HC-HF002: a handler-table dispatch `TABLE[feature_state(state, "flag")]` whose table
        dict literal is missing an entry for one of the flag's FEATURES-declared states — that
        state raises KeyError when the flag enters it (§7). The subscript's index is a
        feature_state call naming a declared flag, and its object is a module-scope name bound
        to a dict literal. Reported at the subscript's line. When FEATURES is not a readable
        module-scope dict literal, or the table resolves to no module-scope dict literal, the
        rule fires nothing."""
        features = features_vocabulary()
        if not features:
            return []
        tables = module_dict_literals()
        findings = []
        for node in nodes:
            if node.type != "subscript":
                continue
            obj = node.child_by_field_name("value")
            index = node.child_by_field_name("subscript")
            if obj is None or index is None or obj.type != "identifier":
                continue
            if index.type != "call":
                continue
            flag = feature_state_flag(index)
            if flag is None or flag not in features:
                continue
            table = tables.get(obj.text.decode("utf-8"))
            if table is None:
                continue
            missing = features[flag] - table
            if not missing:
                continue
            findings.append(
                diagnostic(
                    "HC-HF002",
                    "warning",
                    f"Handler table {obj.text.decode('utf-8')!r} dispatched on feature "
                    f"{flag!r} has no entry for state(s) {sorted(missing)}; the flag entering "
                    "that state raises KeyError. Add the missing entry, or handle the state.",
                    node,
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
        check_p015,
        check_hc008,
        check_hc001,
        check_hc002,
        check_hc_or001,
        check_p017,
        check_hc004,
        check_hc005,
        check_hc010,
        check_hf001,
        check_hf002,
    )

    def parse_directive(comment_node):
        """The suppression directive a comment states, or None when the comment is not one
        (§7.1). A directive reads `honest: <verb> RULE[, RULE...][: reason]`: the verb is one
        of _SUPPRESSION_KEYWORDS, the rules before the first `:` are split on commas and
        spaces, and the reason is the text after that `:`. A comment whose first word is not a
        verb — an ordinary `# honest: profiled` note or any other comment — is not a
        directive."""
        raw = comment_node.text.decode("utf-8") if comment_node.text else ""
        body = raw.lstrip("#").strip()
        if not body.startswith("honest:"):
            return None
        rest = body[len("honest:") :].strip()
        head = rest.split(None, 1)
        if not head or head[0] not in _SUPPRESSION_KEYWORDS:
            return None
        remainder = head[1] if len(head) > 1 else ""
        rule_part, separator, reason_part = remainder.partition(":")
        line, _col = line_col(comment_node)
        return {
            "keyword": head[0],
            "rules": rule_part.replace(",", " ").split(),
            "has_reason": separator == ":" and reason_part.strip() != "",
            "line": line,
            "node": comment_node,
        }

    def suppression_directives():
        """Every suppression directive in the file, in source-line order (§7.1). A disable's
        range depends on the enable that follows it, so the order they are resolved in is the
        order they sit on the page, not the order the walk happens to yield comments."""
        found = [
            parse_directive(node) for node in nodes if node.type == "comment"
        ]
        return sorted(
            (directive for directive in found if directive is not None),
            key=lambda directive: directive["line"],
        )

    def suppression_scopes(directives):
        """The list of suppression scopes the directives open (§7.1, §7.4). An `ignore` opens
        a point scope covering only its own line. A `disable RULE` opens a range from its line
        to the matching `enable RULE` (exclusive), or to end of file when no `enable` closes
        it; a second `disable` of an already-open rule opens no range, so it stays dead. Each
        scope carries the index of the directive that owns it, which is how liveness is
        credited back for HC-SUP001."""
        line_count = source.count("\n") + 1
        scopes = []
        open_ranges = {}
        for index, directive in enumerate(directives):
            keyword = directive["keyword"]
            line = directive["line"]
            if keyword == "ignore":
                for rule in directive["rules"]:
                    scopes.append({"rule": rule, "lo": line, "hi": line, "owner": index})
            elif keyword == "disable":
                for rule in directive["rules"]:
                    if rule not in open_ranges:
                        open_ranges[rule] = (line, index)
            elif keyword == "enable":
                for rule in directive["rules"]:
                    if rule in open_ranges:
                        lo, owner = open_ranges.pop(rule)
                        scopes.append(
                            {"rule": rule, "lo": lo, "hi": line - 1, "owner": owner}
                        )
        for rule, (lo, owner) in open_ranges.items():
            scopes.append({"rule": rule, "lo": lo, "hi": line_count, "owner": owner})
        return scopes

    def diagnostic_line(diag):
        """The 1-based line a diagnostic sits on, read from its 'path:line:col' location, or
        None when the location carries no line. Scope matching compares this against a
        directive's line."""
        parts = diag["source_location"].rsplit(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            return None
        return int(parts[1])

    def apply_suppression(raw_diagnostics):
        """The final pass (§7.4): downgrade each raw diagnostic a directive scope covers to
        info — kept in the list, never dropped — then append HC-SUP001 for a directive that
        suppressed nothing and HC-SUP002 for an `ignore`/`disable` with no reason. The two meta
        findings are independent and both may fire on one directive. HC-SUP001 and HC-SUP002
        are themselves never suppressed: they are appended after the downgrade pass and no
        scope ever covers them, so a directive naming either suppresses nothing and HC-SUP001
        reports it dead."""
        directives = suppression_directives()
        scopes = suppression_scopes(directives)
        live_owners = set()
        adjusted = []
        for diag in raw_diagnostics:
            line = diagnostic_line(diag)
            covering = [
                scope
                for scope in scopes
                if scope["rule"] == diag["rule_id"]
                and line is not None
                and scope["lo"] <= line <= scope["hi"]
            ]
            if not covering:
                adjusted.append(diag)
                continue
            for scope in covering:
                live_owners.add(scope["owner"])
            adjusted.append({**diag, "severity": "info"})
        for index, directive in enumerate(directives):
            if directive["keyword"] == "enable":
                continue
            if index not in live_owners:
                adjusted.append(
                    diagnostic(
                        "HC-SUP001",
                        "error",
                        "Suppression directive suppressed nothing: no named rule fired in its "
                        "scope. Remove the directive, or correct the rule it names.",
                        directive["node"],
                    )
                )
            if not directive["has_reason"]:
                adjusted.append(
                    diagnostic(
                        "HC-SUP002",
                        "error",
                        "Suppression directive carries no reason. Add ': <why the violation "
                        "stands>' so the next reader can judge whether it still holds.",
                        directive["node"],
                    )
                )
        return adjusted

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
    return apply_suppression(diagnostics)


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


def check_references(sources):
    """The pure cross-file reference core of the base-mode CLI path (§HC-REF002,
    §HC-REF003), the whole-set counterpart of check_source for references that resolve
    across files rather than within one.

    sources is a list of SourceFile ({path, text}) — the discovered template, stylesheet
    and script files, already read and paired. A template's `{% include %}` target may
    resolve to any template in the set, and a class a template or script names may be
    defined by any stylesheet, so neither reference is decidable from one file: the whole
    set must be in view. It opens no file and raises nothing — a dead reference comes back
    as an error Diagnostic.

    A template carries both kinds of reference, and no single grammar surfaces both: the
    jinja grammar reads `{% %}` tags but leaves HTML attributes as opaque template_data,
    and the html grammar reads class attributes but leaves `{% %}` as opaque text (§HC-REF002).
    So a template is parsed under jinja for its include/extends targets and under html for
    its class attributes. Stylesheets parse under css, scripts under javascript.

    The per-rule logic is nested here as data, exactly as check_source holds its construction
    rules; HC-REF002 and HC-REF003 are not separately declared functions.
    """

    def finding(rule_id, message, path, node):
        line, col = line_col(node)
        return {
            "rule_id": rule_id,
            "severity": "error",
            "message": message,
            "source_location": f"{path}:{line}:{col}",
            "context": "",
            "fixable": False,
        }

    def root_under(text, grammar):
        """The parse tree root of text read under a named grammar. Unlike check_source's
        parse_source, which detects the grammar from the path, a template is read under two
        grammars whichever extension it carries, so the grammar is chosen here, not detected
        from a path."""
        return parse(text.encode("utf-8"), grammar).root_node

    def basename(path):
        return path.rsplit("/", 1)[-1]

    def literal_text(string_node):
        """The string a jinja `string` node spells, surrounding whitespace and quotes
        stripped."""
        return ast.literal_eval(string_node.text.decode("utf-8").strip())

    def is_interpolated(text):
        return any(marker in text for marker in _INTERPOLATION_MARKERS)

    def js_string_value(string_node):
        """The value a javascript `string` node spells, read from its string_fragment; the
        empty string for a string with no fragment (`""`)."""
        fragment = next(
            (c for c in string_node.named_children if c.type == "string_fragment"), None
        )
        return fragment.text.decode("utf-8") if fragment is not None else ""

    def kind_of(source_file):
        """The reference kind of one source file from the grammar honest-parse detects:
        'template', 'stylesheet', 'script', or None for a file carrying no reference this
        core resolves. A file of an unplaceable extension resolves to None and is ignored."""
        detected = language_of(source_file["path"]).get("ok")
        if detected in _TEMPLATE_GRAMMARS:
            return "template"
        if detected == "css":
            return "stylesheet"
        if detected == "javascript":
            return "script"
        return None

    templates = [s for s in sources if kind_of(s) == "template"]
    stylesheets = [s for s in sources if kind_of(s) == "stylesheet"]
    scripts = [s for s in sources if kind_of(s) == "script"]

    # ---- HC-REF002: template include/extends target resolves to a template ----

    template_paths = {t["path"] for t in templates}
    template_basenames = {basename(path) for path in template_paths}

    def include_resolves(target):
        """Flat path equality against the template files in the set: the target resolves if
        it equals a template file's path or basename, or its own basename matches one
        (§HC-REF002). Nested template-search-root resolution (atoms/, molecules/ sibling
        roots) is out of scope — the .hd and spec do not pin how a pure function derives
        those roots from `sources` alone — so only flat matching is done here."""
        return (
            target in template_paths
            or target in template_basenames
            or basename(target) in template_basenames
        )

    def include_extends_statements(text):
        """(keyword, target, node) for each `{% include %}` / `{% extends %}` whose target
        is a string literal, read under the jinja grammar. A dynamic target (no string
        literal, `{% include some_var %}`) carries nothing to resolve and is skipped."""
        statements = []
        for node in walk(root_under(text, "jinja")):
            if node.type != "statement":
                continue
            tag = node.child_by_field_name("tag")
            if tag is None:
                continue
            keyword = tag.text.decode("utf-8")
            if keyword not in ("include", "extends"):
                continue
            string_node = next(
                (c for c in node.named_children if c.type == "string"), None
            )
            if string_node is None:
                continue
            statements.append((keyword, literal_text(string_node), node))
        return statements

    def check_ref002():
        findings = []
        for template in templates:
            for keyword, target, node in include_extends_statements(template["text"]):
                if include_resolves(target):
                    continue
                findings.append(
                    finding(
                        "HC-REF002",
                        f"template {keyword} target {target!r} resolves to no template among "
                        "the checked files. Add the template, or correct the target.",
                        template["path"],
                        node,
                    )
                )
        return findings

    # ---- HC-REF003: class reference resolves to a defined rule ----

    def defined_classes():
        """The union of class names every stylesheet in the set defines: a `class_name`
        under a `class_selector`, read under the css grammar. The `class_name` of a
        pseudo-class (`:hover`) sits under a pseudo_class_selector, not a class_selector, so
        it is not mistaken for a class."""
        classes = set()
        for sheet in stylesheets:
            for node in walk(root_under(sheet["text"], "css")):
                if (
                    node.type == "class_name"
                    and node.parent is not None
                    and node.parent.type == "class_selector"
                ):
                    classes.add(node.text.decode("utf-8"))
        return classes

    def template_class_tokens(text):
        """(token, node) for each static class token a template emits, read under the html
        grammar. A class value carrying interpolation (`class="card {{ variant }}"`) is
        skipped whole, the stated bound of the check."""
        tokens = []
        for node in walk(root_under(text, "html")):
            if node.type != "attribute":
                continue
            name_node = next(
                (c for c in node.named_children if c.type == "attribute_name"), None
            )
            if name_node is None or name_node.text.decode("utf-8") != "class":
                continue
            value_node = next(
                (c for c in node.named_children if c.type == "quoted_attribute_value"),
                None,
            )
            if value_node is None:
                continue
            inner = next(
                (c for c in value_node.named_children if c.type == "attribute_value"),
                None,
            )
            if inner is None:
                continue
            value_text = inner.text.decode("utf-8")
            if is_interpolated(value_text):
                continue
            for token in value_text.split():
                tokens.append((token, value_node))
        return tokens

    def classlist_tokens(call_node):
        """The class tokens one call contributes when it is a classList method call
        (el.classList.<method>(...)): each string-literal argument is one class token. A
        non-literal argument carries no literal and is skipped; a call that is not a
        classList method call contributes nothing."""
        function = call_node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            return []
        method = function.child_by_field_name("property")
        receiver = function.child_by_field_name("object")
        if method is None or method.text.decode("utf-8") not in _CLASSLIST_METHODS:
            return []
        if receiver is None or receiver.type != "member_expression":
            return []
        receiver_property = receiver.child_by_field_name("property")
        if (
            receiver_property is None
            or receiver_property.text.decode("utf-8") != "classList"
        ):
            return []
        arguments = call_node.child_by_field_name("arguments")
        if arguments is None:
            return []
        return [
            (js_string_value(argument), call_node)
            for argument in arguments.named_children
            if argument.type == "string"
        ]

    def classname_tokens(assignment_node):
        """The class tokens one assignment contributes when it assigns a string literal to a
        `.className` property: each whitespace-separated token of the string. A non-literal
        right-hand side carries no literal and is skipped."""
        left = assignment_node.child_by_field_name("left")
        right = assignment_node.child_by_field_name("right")
        if left is None or left.type != "member_expression":
            return []
        if right is None or right.type != "string":
            return []
        left_property = left.child_by_field_name("property")
        if left_property is None or left_property.text.decode("utf-8") != "className":
            return []
        return [(token, assignment_node) for token in js_string_value(right).split()]

    def script_class_tokens(text):
        """(token, node) for each static class a script names, read under the javascript
        grammar: a string-literal argument to a classList method and each token of a
        className string-literal assignment."""
        tokens = []
        for node in walk(root_under(text, "javascript")):
            if node.type == "call_expression":
                tokens.extend(classlist_tokens(node))
            elif node.type == "assignment_expression":
                tokens.extend(classname_tokens(node))
        return tokens

    def check_ref003():
        classes = defined_classes()
        findings = []

        def report(source_file, tokens):
            return [
                finding(
                    "HC-REF003",
                    f"class {token!r} resolves to no rule any stylesheet defines. Define "
                    "the class, or correct the reference.",
                    source_file["path"],
                    node,
                )
                for token, node in tokens
                if token not in classes
            ]

        for template in templates:
            findings.extend(report(template, template_class_tokens(template["text"])))
        for script in scripts:
            findings.extend(report(script, script_class_tokens(script["text"])))
        return findings

    return check_ref002() + check_ref003()
