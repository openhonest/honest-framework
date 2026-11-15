"""Purity, mutation and body-shape analysis (§4.2, §5.4, §HC008, §HC-P014). Each
reads structure off a node and answers data; the node kind keys a closed handler
table and every other decision is boolean algebra."""

from honest_parse import walk

from ._util import choose, pick, read_or
from .nodes import _field, bare_or_final_name, literal_string, param_names

_IMMUTABLE_TYPES = {"integer", "float", "string", "true", "false", "none", "tuple"}


def is_immutable_value(node):
    """True when a value is provably immutable — a number, string, bool, None, a
    tuple literal, a negated immutable, or a frozenset(...) call (§5.4)."""
    return pick(
        node.type in _IMMUTABLE_TYPES,
        lambda: True,
        lambda: pick(
            node.type == "unary_operator",
            lambda: is_immutable_value(node.named_children[-1]),
            lambda: _is_frozenset_call(node),
        ),
    )


def _is_frozenset_call(node):
    return bool(
        node.type == "call"
        and bare_or_final_name(_field(node, "function")) == "frozenset"
    )


def _first_child(node):
    return pick(len(node.named_children) == 0, lambda: None, lambda: node.named_children[0])


def _left_identifier(assignment):
    left = _field(assignment, "left")
    return choose(left is not None and left.type == "identifier", left, None)


def module_mutable_globals(ctx):
    """The module-level names bound to a not-provably-immutable value — the impure
    globals (§5.4, §HC008). Imported and def/class names are never assignment
    targets, so they fall out."""
    top = ctx["root"].named_children
    expressions = filter(lambda s: s.type == "expression_statement", top)
    assignments = filter(
        lambda a: a is not None and a.type == "assignment",
        map(_first_child, expressions),
    )
    mutable = filter(
        lambda a: _left_identifier(a) is not None
        and not is_immutable_value(_field(a, "right")),
        assignments,
    )
    return set(map(lambda a: _left_identifier(a).text.decode("utf-8"), mutable))


def _all_param_names(fdef):
    params = _field(fdef, "parameters")
    children = pick(params is None, lambda: [], lambda: list(params.named_children))
    out = []
    for param in children:
        out.extend(param_names(param))
    return out


def _assigned_in(node):
    names = set()
    assignment = choose(node.type == "assignment", node, None)
    left = _field(assignment, "left")
    names.update(
        pick(
            left is not None and left.type == "identifier",
            lambda: {left.text.decode("utf-8")},
            lambda: set(),
        )
    )
    for child in node.named_children:
        names.update(_assigned_in(child))
    return names


def link_locals(fdef, body):
    """The names local to a link — its parameters plus the names it assigns in its
    own body (§5.4)."""
    names = set(_all_param_names(fdef))
    for statement in body:
        names.update(_assigned_in(statement))
    return names


def _entry_matches(entry, text):
    return bool(
        entry == text
        or _prefix_star(entry, text)
        or _segment_match(entry, text)
    )


def _prefix_star(entry, text):
    return bool(
        entry.endswith("*")
        and not entry.endswith(".*")
        and text.startswith(entry[:-1])
    )


def _segment_match(entry, text):
    entry_segments = entry.split(".")
    text_segments = text.split(".")
    return bool(
        "*" in entry_segments
        and len(entry_segments) == len(text_segments)
        and all(
            e == "*" or e == t
            for e, t in zip(entry_segments, text_segments)
        )
    )


def watched(target, watch):
    """True when a call's dotted target matches a watch entry — exact, a trailing
    `*` prefix, or a `*` segment glob (§5.4)."""
    text = target.text.decode("utf-8")
    return any(_entry_matches(entry, text) for entry in watch)


_CALL_TYPES = {"call", "call_expression"}


def _own_body_nodes(fdef):
    from .nodes import own_body

    return own_body(fdef)


def link_is_impure(ctx, fdef, watch, mutable_globals):
    """True when a link's own body calls a watched function or reads a module-level
    mutable global, nested scopes not descended into (§HC008)."""
    body = _own_body_nodes(fdef)
    calls = filter(lambda n: n.type in _CALL_TYPES, body)
    hits_watch = any(_calls_watched(ctx, c, watch) for c in calls)
    reads_global = any(_reads_global(ctx, n, mutable_globals) for n in body)
    return bool(hits_watch or reads_global)


def _calls_watched(ctx, call_node, watch):
    func = _field(call_node, "function")
    return pick(func is None, lambda: False, lambda: watched(func, watch))


def _reads_global(ctx, node, mutable_globals):
    from .nodes import is_attribute_suffix, is_keyword_name

    return bool(
        node.type == "identifier"
        and node.text.decode("utf-8") in mutable_globals
        and not is_attribute_suffix(node)
        and not is_keyword_name(node)
    )


def has_decorator(ctx, fdef, name):
    from .decorators import has_decorator as _has

    return _has(ctx, fdef, name)


def local_function_links(ctx):
    """Each file-local function mapped to whether it carries a @link decorator
    (§4.2, HC001)."""
    from .decorators import has_decorator as _has

    functions = filter(
        lambda n: n.type == "function_definition",
        ctx["root"].named_children
        + _decorated_functions(ctx),
    )
    return {
        _field(fdef, "name").text.decode("utf-8"): _has(ctx, fdef, "link")
        for fdef in functions
    }


def _decorated_functions(ctx):
    decorated = filter(
        lambda n: n.type == "decorated_definition", ctx["root"].named_children
    )
    inner = map(
        lambda d: next(
            filter(lambda c: c.type == "function_definition", d.named_children), None
        ),
        decorated,
    )
    return [f for f in filter(lambda f: f is not None, inner)]


def _signature(node):
    return choose(
        node.type == "identifier",
        ("identifier", node.text.decode("utf-8")),
        (node.type, tuple(_signature(c) for c in node.named_children)),
    )


def canonical_body(fdef):
    """A function body's structural signature with every literal blanked; an
    identifier keeps its name (§HC-P014)."""
    block = _field(fdef, "body")
    return pick(block is None, lambda: (), lambda: _signature(block))


def body_has_call(fdef):
    """True when a function's own body contains a call (§HC-P014)."""
    return any(n.type in _CALL_TYPES for n in _own_body_nodes(fdef))


def body_statement_count(fdef):
    """The count of statements in a function's own body, nested scopes counted as
    one and not descended into (§HC-P014)."""
    block = _field(fdef, "body")
    return pick(block is None, lambda: 0, lambda: len(block.named_children))


def longest_shared_run(ctx, calls_a, calls_b):
    """The length of the longest run of consecutive equivalent call names two
    sequences share (§HC-OR003)."""
    best = 0
    previous = [0] * (len(calls_b) + 1)
    for i in range(1, len(calls_a) + 1):
        current = [0] * (len(calls_b) + 1)
        for j in range(1, len(calls_b) + 1):
            current[j] = choose(calls_a[i - 1] == calls_b[j - 1], previous[j - 1] + 1, 0)
            best = max(best, current[j])
        previous = current
    return best


_EMPTY_CONSTRUCTORS = {"list", "dict", "set", "tuple", "frozenset"}


def _number_is_zero(value):
    return float(value.text.decode("utf-8")) == 0.0


def _empty_container(value):
    return len(value.named_children) == 0


def _is_empty_constructor(value):
    name = bare_or_final_name(_field(value, "function"))
    args = _field(value, "arguments")
    count = pick(args is None, lambda: 0, lambda: len(args.named_children))
    return bool(name in _EMPTY_CONSTRUCTORS and count == 0)


_EMPTY_DEFAULT_HANDLERS = {
    "none": lambda v: True,
    "false": lambda v: True,
    "integer": _number_is_zero,
    "float": _number_is_zero,
    "string": lambda v: literal_string(v) == "",
    "list": _empty_container,
    "dictionary": _empty_container,
    "set": _empty_container,
    "tuple": _empty_container,
    "parenthesized_expression": _empty_container,
    "call": _is_empty_constructor,
}


def _default_false(value):
    return False


def is_empty_default(ctx, value):
    """True when a parameter default stands for absence — None, False, a zero
    number, an empty string, an empty container literal or an empty-constructor call
    (§HC-P015)."""
    return read_or(_EMPTY_DEFAULT_HANDLERS, value.type, _default_false)(value)


_NUMERIC_COERCERS = {"int", "float"}
_DIVISION_OPERATORS = {"/", "//"}


def _is_bare_numeric_call(node):
    return bool(
        node.type == "call"
        and bare_or_final_name(_field(node, "function")) in _NUMERIC_COERCERS
    )


def _operator_text(node):
    operator = _field(node, "operator")
    return pick(
        operator is None,
        lambda: "",
        lambda: operator.text.decode("utf-8"),
    )


def _is_division(node):
    return bool(node.type == "binary_operator" and _operator_text(node) in _DIVISION_OPERATORS)


def _risky_node(node):
    return bool(
        _is_bare_numeric_call(node)
        or node.type == "subscript"
        or _is_division(node)
    )


def predicate_is_risky(value):
    """True when a predicate's expression holds a node that throws on a non-matching
    input — a bare int()/float() call, a subscript, or a `/`//`//` division
    (§HC009)."""
    return any(_risky_node(n) for n in walk(value))
