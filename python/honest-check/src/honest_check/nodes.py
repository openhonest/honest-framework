"""honest-check AST helper layer: nodes (split from core.py for L1.17).

Each helper takes the check context ctx (root, nodes, aliases, roles, source, path, rule_config)
and returns data; the rule logic that uses them stays nested-as-data in the sub-cores (section 3.4)."""

import fnmatch
import ast
from honest_parse import line_col, walk
from honest_check.constants import _CONSTRUCTORS, _DOOR_ROLES, _INNER_SCOPES


def diagnostic(ctx, rule_id, severity, message, node):
    path = ctx["path"]
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


def string_members(ctx, node):
    """The string values a set/list/tuple node holds, in source order."""
    return [
        literal_string(child)
        for child in node.named_children
        if child.type == "string"
    ]


def call_arguments(ctx, call_node):
    """The (positional nodes, keyword name -> value node) of a call."""
    argument_list = call_node.child_by_field_name("arguments")
    positionals = []
    keywords = {}
    for child in argument_list.named_children:
        if child.type == "keyword_argument":
            name = child.child_by_field_name("name").text.decode("utf-8")
            keywords[name] = child.child_by_field_name("value")
        else:
            positionals.append(child)
    return positionals, keywords


def import_aliases(ctx):
    """Map each local name bound by a honest_type import to its canonical constructor
    name (section 3.3), so a call under an alias resolves to the real constructor."""
    nodes = ctx["nodes"]
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


def canonical_name(ctx, call_node):
    """The constructor name a call resolves to, or None when the call is not a framework
    constructor. A direct constructor-name call counts, and an aliased one resolves
    through the import (section 3.3)."""
    aliases = ctx["aliases"]
    function = call_node.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    name = function.text.decode("utf-8")
    if name in aliases:
        return aliases[name]
    if name in _CONSTRUCTORS:
        return name
    return None


def base_types_of(ctx, dictionary_node):
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
            base_types[name] = ("set", frozenset(string_members(ctx, value)))
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


def called_name(ctx, call_node):
    """The name a call invokes — a bare identifier, or the final attribute of a dotted
    call such as `window.addEventListener` — or None (§HC-P011)."""
    function = call_node.child_by_field_name("function")
    if function.type == "identifier":
        return function.text.decode("utf-8")
    if function.type == "attribute":
        attr = function.child_by_field_name("attribute")
        return attr.text.decode("utf-8") if attr is not None else None
    return None


def own_body(fdef):
    """The body descendants belonging to a function itself, not descending into a deeper
    nested def, lambda or decorated def — those statements are the inner scope's own
    (§4.2). A `nonlocal` and a mutation count only where they sit directly in this body."""
    body = fdef.child_by_field_name("body")
    found = []

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
            names.add(child.text.decode("utf-8"))
    return names


def decorators_of(ctx, fdef):
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
    `@`. A parsed decorator always carries that expression as its first named child."""
    return decorator.named_children[0]


def decorator_target(decorator):
    """The final name a decorator names — `boundary` from `@boundary`, `lru_cache` from
    `@functools.lru_cache(maxsize=1)` — or None when it is neither a plain nor a dotted
    name, called or bare (§4.2, §5.6)."""
    expr = decorator_expression(decorator)
    if expr.type == "call":
        expr = expr.child_by_field_name("function")
    if expr.type == "identifier":
        return expr.text.decode("utf-8")
    if expr.type == "attribute":
        attr = expr.child_by_field_name("attribute")
        return attr.text.decode("utf-8") if attr is not None else None
    return None


def is_boundary_decorator(ctx, decorator):
    """True when a decorator declares its function a boundary — `@boundary` (bare or
    called) or `@link(boundary=True)` (§4.2)."""
    expr = decorator_expression(decorator)
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
        _positionals, keywords = call_arguments(ctx, expr)
        value = keywords.get("boundary")
        return value is not None and value.type == "true"
    return False


def in_non_boundary_function(ctx, node):
    """True when a node's nearest enclosing function exists, carries no boundary decorator,
    and the declaration gives its name no door role — the scope HC-P002, HC-P004 and
    HC-P005 fire in (§4.2, §5.4, §5.5). A node at module scope, or in a boundary function,
    is not in a non-boundary function.

    The decorator signal is primary: a boundary decorator makes the function a boundary
    outright. Only where the decorator check found the function non-boundary — the function
    the rule is about to flag — is the declaration consulted, and only then: when the .hd
    marks that same function boundary_in, boundary_out or reader, it is treated as a
    boundary and the finding does not fire (honest-check.hd). With no declaration (the empty
    role map) or a non-door role, the decorator verdict stands."""
    roles_by_name = ctx["roles"]
    function = enclosing_function(node)
    if function is None:
        return False
    if any(is_boundary_decorator(ctx, d) for d in decorators_of(ctx, function)):
        return False
    name_node = function.child_by_field_name("name")
    name = name_node.text.decode("utf-8") if name_node else None
    role = roles_by_name[name] if name in roles_by_name else None
    return role not in _DOOR_ROLES


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


def module_mutable_globals(ctx):
    """The module-level names bound to a mutable (or not provably immutable) value — the
    globals a read of which makes a link impure (§5.4, §872). A name bound to an immutable
    value, and an imported or def/class name (never an assignment target), are not here."""
    root = ctx["root"]
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
    for child in params.named_children:
        names |= param_names(child)
    for node in body:
        if node.type in ("assignment", "augmented_assignment"):
            target = node.child_by_field_name("left")
            if target is not None and target.type == "identifier":
                names.add(target.text.decode("utf-8"))
    return names


def node_is_field_child(node, parent_type, field_name):
    """True when a node is the named field of a parent of the given type (§5.4).

    Two reads use it: the attribute part of an `x.name` access (parent_type 'attribute', field
    'attribute') — the `.name`, not a read of `name` itself, so `config.timeout` reads `config`,
    not a global `timeout`; and the name of a keyword argument, the `k` in `f(k=v)` (parent_type
    'keyword_argument', field 'name'), which names a parameter of the callee, not a global. In
    each the identifier names a part of its parent, so the global-read rules skip it."""
    parent = node.parent
    return (
        parent is not None
        and parent.type == parent_type
        and parent.child_by_field_name(field_name) == node
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
