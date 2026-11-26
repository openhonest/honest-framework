"""Purity, mutation and body-shape analysis (§4.2, §5.4, §HC008, §HC-P014). Each
reads structure off a node and answers data; the node kind keys a closed handler
table and every other decision is boolean algebra."""

import re

from honest_parse import language_of, walk

from ._util import choose, pick, read_or
from .nodes import _field, _text, bare_or_final_name, literal_string, param_names

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


# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched -> test=python/honest-check/conformance/probe_watched.py::probe_watched
# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched resolves static JavaScript member names independent of spacing -> test=python/honest-check/conformance/probe_watched_javascript_members.py::probe_watched_javascript_members
# inherits: hd=python/honest-check/honest-check.hd::watched -> feature=specs/features/honest-check.feature::watched matches static Ruby methods and Go selectors -> test=python/honest-check/conformance/probe_p004_watched_ruby_go.py::probe_p004_watched_ruby_go
# hd: watched
def watched(target, watch):
    """Match the spelling of a call target or supplied read reference (§5.4)."""
    member = target.type == "member_expression"
    match target.type:
        case "subscript_expression":
            return False
    parts = []
    node = target
    static = True
    method = _field(target, "method")
    match target.type, method is not None:
        case "call", True:
            receiver = _field(target, "receiver")
            static = receiver is None or receiver.type in {"identifier", "constant"} or (
                receiver.type == "scope_resolution"
                and all(not piece.is_named or piece.type in {"scope_resolution", "constant"} for piece in walk(receiver))
            )
            prefix = "".join((_text(receiver) or "").split())
            parts = list(filter(bool, (_text(method), prefix)))
            node = None
        case "selector_expression", _:
            operand = _field(target, "operand")
            field = _field(target, "field")
            static = operand is not None and operand.type == "identifier" and field is not None
            parts = [_text(field), _text(operand)]
            node = None
    while node is not None and node.type == "member_expression":
        property_node = _field(node, "property")
        static = static and property_node is not None and property_node.type == "property_identifier"
        parts.append(_text(property_node))
        node = _field(node, "object")
    match not static or (member and (node is None or node.type != "identifier")):
        case True:
            return False
    text = ".".join(reversed(list(filter(bool, [*parts, _text(node)]))))
    return any(_entry_matches(entry, text) for entry in watch)


_CALL_TYPES = {"call", "call_expression"}
_PYTHON_WATCHED_READS = {"os.environ", "sys.argv", "sys.version", "sys.path", "__file__", "__name__"}
_JAVASCRIPT_WATCHED_READS = {"process.env", "process.argv", "process.pid", "process.platform", "process.version", "document.cookie"}


def _own_body_nodes(fdef):
    from .nodes import own_body

    return own_body(fdef)


# inherits: hd=python/honest-check/honest-check.hd::link_is_impure -> feature=specs/features/honest-check.feature::link_is_impure -> test=python/honest-check/conformance/probe_link_is_impure.py::probe_link_is_impure
# inherits: hd=python/honest-check/honest-check.hd::link_is_impure -> feature=specs/features/honest-check.feature::link_is_impure detects watched JavaScript calls and value reads -> test=python/honest-check/conformance/probe_link_is_impure_javascript.py::probe_link_is_impure_javascript
# hd: link_is_impure
def link_is_impure(ctx, fdef, watch, mutable_globals):
    """Find watched calls and reads or mutable global reads in the link's own body."""
    from .nodes import is_attribute_suffix, is_keyword_name

    body = _own_body_nodes(fdef)
    calls = filter(lambda n: n.type in _CALL_TYPES, body)
    hits_watch = any(_calls_watched(ctx, c, watch) for c in calls)
    reads_global = any(_reads_global(ctx, n, mutable_globals) for n in body)
    language = read_or(language_of(ctx["path"]), "ok", "python")
    read_entries = {"python": _PYTHON_WATCHED_READS, "javascript": _JAVASCRIPT_WATCHED_READS}
    read_nodes = {"python": {"attribute", "identifier"}, "javascript": {"member_expression"}}
    watched_reads = watch & read_or(read_entries, language, set())
    reference_types = read_or(read_nodes, language, set())
    references = filter(
        lambda node: watched_reads and node.type in reference_types
        and not is_attribute_suffix(node) and not is_keyword_name(node)
        and watched(node, watched_reads),
        body,
    )
    target_fields = {
        "assignment": "left",
        "for_statement": "left",
        "for_in_clause": "left",
        "named_expression": "name",
        "as_pattern": "alias",
        "aliased_import": "alias",
        "assignment_expression": "left",
        "for_in_statement": "left",
        "variable_declarator": "name",
    }
    wrappers = {
        "pattern_list", "tuple_pattern", "list_pattern", "list_splat_pattern", "as_pattern_target",
        "array_pattern", "object_pattern", "pair_pattern", "rest_pattern",
    }
    for reference in references:
        target = reference
        parent = target.parent
        while parent.type in wrappers:
            target = parent
            parent = target.parent
        field = read_or(target_fields, parent.type, "")
        write_only = (
            parent.type in {"delete_statement", "global_statement", "nonlocal_statement"}
            or target == _field(parent, field)
            or (parent.type == "unary_expression" and _text(_field(parent, "operator")) == "delete")
        )
        match write_only:
            case False:
                return True
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
_PREFIXED_ZERO = re.compile(rb"0[xXoObB]_?0(?:_?0)*")
_DECIMAL_DIGITS = rb"[0-9](?:_?[0-9])*"
_DECIMAL_NUMBER = re.compile(
    rb"((?:" + _DECIMAL_DIGITS + rb"(?:\.(?:" + _DECIMAL_DIGITS + rb")?)?|\." + _DECIMAL_DIGITS
    + rb")(?:[eE][+-]?" + _DECIMAL_DIGITS + rb")?)[jJ]?"
)


# inherits: hd=python/honest-check/honest-check.hd::_number_is_zero -> feature=specs/features/honest-check.feature::_number_is_zero recognizes zero by literal value and syntax -> test=python/honest-check/conformance/probe_number_is_zero_numeric_zero.py::probe_number_is_zero_numeric_zero
# hd: _number_is_zero
def _number_is_zero(value):
    """Recognize Python zero-valued numeric literals under grouping and signs."""
    node = value
    while node is not None:
        match node.type:
            case "integer" | "float":
                raw = node.text
                decimal = _DECIMAL_NUMBER.fullmatch(raw)
                return _PREFIXED_ZERO.fullmatch(raw) is not None or (
                    decimal is not None and float(decimal[1]) == 0.0
                )
            case "parenthesized_expression":
                expressions = list(filter(lambda child: child.type != "comment", node.named_children))
                node = choose(len(expressions) == 1, next(iter(expressions), None), None)
            case "unary_operator":
                sign = _text(_field(node, "operator"))
                node = choose(sign in {"+", "-"}, _field(node, "argument"), None)
            case _:
                break
    return False


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
    "parenthesized_expression": _number_is_zero,
    "unary_operator": _number_is_zero,
    "call": _is_empty_constructor,
}


def _default_false(value):
    return False


# inherits: hd=python/honest-check/honest-check.hd::is_empty_default -> feature=specs/features/honest-check.feature::is_empty_default accepts zero spellings and rejects nonzero defaults -> test=python/honest-check/conformance/probe_is_empty_default_numeric_zero.py::probe_is_empty_default_numeric_zero
# hd: is_empty_default
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
