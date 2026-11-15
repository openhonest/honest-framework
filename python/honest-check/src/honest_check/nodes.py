"""The shared AST-reading helper layer (section 3.4). Each function reads one fact
off a parsed tree-sitter node and returns it as data; none runs the code it reads,
and none branches with an `if` — the node kind is a key into a closed handler
table, and every other decision is boolean algebra or the two-row `pick`."""

from ._util import choose, pick, read_or

# The framework construction calls canonical_name resolves a call site to.
_CONSTRUCTORS = {
    "vocabulary", "binding", "chain", "composed", "state_machine",
}


def _field(node, name):
    """node.child_by_field_name(name), or None when node is None or has no such
    field."""
    return pick(node is None, lambda: None, lambda: node.child_by_field_name(name))


def _text(node):
    """A node's source text decoded, or None when node is None."""
    return pick(node is None, lambda: None, lambda: node.text.decode("utf-8"))


_NAME_READERS = {
    "identifier": lambda n: n.text.decode("utf-8"),
    "attribute": lambda n: n.child_by_field_name("attribute").text.decode("utf-8"),
}


def bare_or_final_name(node):
    """The name a call-or-decorator head resolves to: a bare identifier's text, the
    final attribute of a dotted head, or None for any other shape (a call result, a
    subscript)."""
    return pick(
        node is None,
        lambda: None,
        lambda: read_or(_NAME_READERS, node.type, _no_name)(node),
    )


def _no_name(node):
    return None


def literal_string(node):
    """The Python string a `string` node spells, outer quotes stripped."""
    return node.text.decode("utf-8")[1:-1]


def string_members(ctx, node):
    """The string values a set/list/tuple node holds, in source order."""
    strings = filter(lambda c: c.type == "string", node.named_children)
    return [literal_string(s) for s in strings]


def call_arguments(ctx, call_node):
    """The split argument view of a call: {positionals, keywords}."""
    args = _field(call_node, "arguments")
    members = pick(args is None, lambda: [], lambda: list(args.named_children))
    positionals = [m for m in filter(lambda m: m.type != "keyword_argument", members)]
    keywords = {
        kw.child_by_field_name("name").text.decode("utf-8"): kw.child_by_field_name("value")
        for kw in filter(lambda m: m.type == "keyword_argument", members)
    }
    return {"positionals": positionals, "keywords": keywords}


def called_name(ctx, call_node):
    """The name a call invokes — a bare identifier or the final dotted attribute —
    or None for a call on a call's result (HC-P011)."""
    return bare_or_final_name(_field(call_node, "function"))


def _is_dotted(node):
    """True when node is a plain-or-dotted name chain (identifier, or an attribute
    whose object is itself one)."""
    return pick(
        node is None,
        lambda: False,
        lambda: pick(
            node.type == "identifier",
            lambda: True,
            lambda: pick(
                node.type == "attribute",
                lambda: _is_dotted(node.child_by_field_name("object")),
                lambda: False,
            ),
        ),
    )


def dotted_target(ctx, call_node):
    """The full dotted name a call invokes (`os.system`, `urllib.request.urlopen`),
    or None when the target is not a plain-or-dotted name (HC008)."""
    func = _field(call_node, "function")
    return pick(_is_dotted(func), lambda: func.text.decode("utf-8"), lambda: None)


def canonical_name(ctx, call_node):
    """The framework constructor name a call resolves to (direct or alias-resolved),
    or None when it is no framework constructor (section 3.3)."""
    raw = bare_or_final_name(_field(call_node, "function"))
    resolved = read_or(ctx["aliases"], raw, raw)
    return choose(resolved in _CONSTRUCTORS, resolved, None)


def enclosing_function(node):
    """The nearest enclosing function_definition, climbing parents, or None at
    module scope."""
    parent = node.parent
    return pick(
        parent is None,
        lambda: None,
        lambda: pick(
            parent.type == "function_definition",
            lambda: parent,
            lambda: enclosing_function(parent),
        ),
    )


_SCOPE_BOUNDARIES = {"function_definition", "lambda", "decorated_definition"}


def own_body(fdef):
    """The descendants belonging to a function's own body, not descending into a
    nested def, lambda or decorated def (§4.2)."""
    block = _field(fdef, "body")
    return pick(block is None, lambda: [], lambda: _descend(block))


def _descend(node):
    out = []
    for child in node.named_children:
        out.append(child)
        out.extend(
            pick(
                child.type in _SCOPE_BOUNDARIES,
                lambda: [],
                lambda: _descend(child),
            )
        )
    return out


_PARAM_NAME_READERS = {
    "identifier": lambda p: [p.text.decode("utf-8")],
    "default_parameter": lambda p: [p.child_by_field_name("name").text.decode("utf-8")],
    "typed_default_parameter": lambda p: [p.child_by_field_name("name").text.decode("utf-8")],
    "typed_parameter": lambda p: _first_identifier_name(p),
}


def _first_identifier_name(param):
    ident = next(filter(lambda c: c.type == "identifier", param.named_children), None)
    return pick(ident is None, lambda: [], lambda: [ident.text.decode("utf-8")])


def param_names(param):
    """The names a single parameter binds — one for a bare, typed or defaulted
    parameter, none for a splat or other shape."""
    return read_or(_PARAM_NAME_READERS, param.type, _no_param_names)(param)


def _no_param_names(param):
    return []


def is_attribute_suffix(node):
    """True when an identifier is the `.name` suffix of an x.name access (§5.4)."""
    parent = node.parent
    return bool(
        parent is not None
        and parent.type == "attribute"
        and parent.child_by_field_name("attribute") == node
    )


def is_keyword_name(node):
    """True when an identifier is the name of a keyword argument (§5.4)."""
    parent = node.parent
    return bool(
        parent is not None
        and parent.type == "keyword_argument"
        and parent.child_by_field_name("name") == node
    )


def _norm_guard(text):
    return text.replace("'", '"').replace(" ", "")


def is_main_guard(ctx, node):
    """True when node is exactly the `if __name__ == "__main__":` script guard, the
    one `if` HC-P001 exempts (§4.2 §HC-P001)."""
    condition = pick(
        node.type == "if_statement",
        lambda: _field(node, "condition"),
        lambda: None,
    )
    return bool(
        condition is not None
        and _norm_guard(condition.text.decode("utf-8")) == '__name__=="__main__"'
    )


def _function_name(fdef):
    return _text(_field(fdef, "name"))


def within_class_init(ctx, node):
    """True when a node's nearest enclosing function is an `__init__` method of a
    class (§4.2, HC-P007)."""
    fn = enclosing_function(node)
    return bool(
        fn is not None
        and _function_name(fn) == "__init__"
        and _is_class_method(fn)
    )


def _is_class_method(fdef):
    block = fdef.parent
    owner = pick(block is None, lambda: None, lambda: block.parent)
    return bool(owner is not None and owner.type == "class_definition")


def underscore_self_name(target):
    """The attribute name of a `self._name` assignment target, or None when the
    target is not that shape (§HC-P007)."""
    obj = _field(target, "object")
    attr = _field(target, "attribute")
    name = _text(attr)
    is_self_underscore = bool(
        target.type == "attribute"
        and _text(obj) == "self"
        and name is not None
        and name.startswith("_")
    )
    return choose(is_self_underscore, name, None)


_MUTATION_TYPES = {"assignment", "augmented_assignment"}


def mutated_names(ctx, statements):
    """The plain-identifier names assignments and augmented assignments target
    directly (§4.2)."""
    assigns = filter(lambda n: n.type in _MUTATION_TYPES, statements)
    lefts = map(lambda n: n.child_by_field_name("left"), assigns)
    idents = filter(lambda left: left is not None and left.type == "identifier", lefts)
    return set(map(lambda left: left.text.decode("utf-8"), idents))


def nonlocal_names(statements):
    """The names the `nonlocal` statements directly in a body declare."""
    declarations = filter(lambda n: n.type == "nonlocal_statement", statements)
    names = set()
    for declaration in declarations:
        idents = filter(lambda c: c.type == "identifier", declaration.named_children)
        names.update(map(lambda c: c.text.decode("utf-8"), idents))
    return names
