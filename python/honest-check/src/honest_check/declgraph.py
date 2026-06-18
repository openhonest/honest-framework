"""Declaration graph — extract honest-type constructor calls (sections 3.3-3.4).

Rules in the construction and chain tiers operate on declared honest-type objects,
not on raw syntax. This module turns source into those declarations: it resolves
how honest_type was imported (section 3.3), finds the constructor calls
(`vocabulary`, `binding`, `composed`, `chain`, `state_machine`, `link`), and reads
their arguments into plain dicts. Pure: parsing in, data out.

A recognizer is tagged by kind so rules can reason about it without re-parsing:
    ("set", frozenset(members))   a bounded Set recognizer
    ("predicate", node)           a predicate(...) / callable recognizer (unbounded)
    ("ref", name)                 a bare name referring to a recognizer defined elsewhere
"""

from honest_check.parse import line_col, node_text, walk

_HONEST_TYPE_NAMES = frozenset(
    {"vocabulary", "binding", "composed", "chain", "link", "predicate", "state_machine"}
)


def resolve_aliases(root, source: bytes):
    """How honest_type was imported. Returns (names, modules) per section 3.3.

    names   {local_name: canonical}  for `from honest_type import chain [as c]`
    modules {local_module_name}      for `import honest_type [as ht]` (ht.chain(...))
    """
    names: dict[str, str] = {}
    modules: set[str] = set()
    for node in walk(root):
        if node.type == "import_from_statement":
            module = node.child_by_field_name("module_name")
            if module is None or "honest_type" not in node_text(module, source):
                continue
            for child in node.named_children:
                if child is module:
                    continue
                if child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    alias = child.child_by_field_name("alias")
                    if name is not None and alias is not None:
                        canonical = node_text(name, source)
                        if canonical in _HONEST_TYPE_NAMES:
                            names[node_text(alias, source)] = canonical
                if child.type == "dotted_name":
                    canonical = node_text(child, source)
                    if canonical in _HONEST_TYPE_NAMES:
                        names[canonical] = canonical
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    alias = child.child_by_field_name("alias")
                    if name is not None and alias is not None and "honest_type" in node_text(name, source):
                        modules.add(node_text(alias, source))
                if child.type == "dotted_name" and node_text(child, source) == "honest_type":
                    modules.add("honest_type")
    return names, modules


def constructor_calls(root, source: bytes, aliases, canonical: str):
    """Every call node invoking the named honest-type constructor (section 3.4)."""
    names, modules = aliases
    out = []
    for node in walk(root):
        if node.type != "call":
            continue
        fn = node.child_by_field_name("function")
        if fn is None:
            continue
        if fn.type == "identifier" and names.get(node_text(fn, source)) == canonical:
            out.append(node)
        if fn.type == "attribute":
            obj = fn.child_by_field_name("object")
            attr = fn.child_by_field_name("attribute")
            if obj is None or attr is None:
                continue
            if (
                obj.type == "identifier"
                and node_text(obj, source) in modules
                and node_text(attr, source) == canonical
            ):
                out.append(node)
    return out


def assigned_name(call_node, source: bytes):
    """The variable a constructor call is assigned to, for messages, or None."""
    parent = call_node.parent
    if parent is not None and parent.type == "assignment":
        left = parent.child_by_field_name("left")
        if left is not None and left.type == "identifier":
            return node_text(left, source)
    return None


def string_value(node, source: bytes):
    """The text inside a string literal node, or None if the node is not a string."""
    if node.type != "string":
        return None
    for child in node.named_children:
        if child.type == "string_content":
            return node_text(child, source)
    return ""


def _recognizer(value_node, source: bytes):
    """Tag a vocabulary value node as ('set'|'predicate'|'ref', payload)."""
    if value_node.type == "set":
        members = frozenset(
            member
            for member in (string_value(e, source) for e in value_node.named_children)
            if member is not None
        )
        return ("set", members)
    if value_node.type == "identifier":
        return ("ref", node_text(value_node, source))
    return ("predicate", value_node)


def _dictionary_arg(call_node):
    """The first dictionary literal argument of a call, or None."""
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return None
    for child in args.named_children:
        if child.type == "dictionary":
            return child
    return None


def vocabulary_base_types(call_node, source: bytes) -> dict:
    """{type_name: recognizer} for a vocabulary({...}) call (sections 4.2)."""
    dict_node = _dictionary_arg(call_node)
    if dict_node is None:
        return {}
    base_types: dict = {}
    for pair in dict_node.named_children:
        if pair.type != "pair":
            continue
        key = pair.child_by_field_name("key")
        value = pair.child_by_field_name("value")
        if key is None or value is None:
            continue
        type_name = string_value(key, source)
        if type_name is None:
            continue
        base_types[type_name] = _recognizer(value, source)
    return base_types


def positional_arg_count(call_node) -> int:
    """Number of positional arguments (excludes keyword args and comments)."""
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return 0
    return sum(
        1
        for child in args.named_children
        if child.type not in ("comment", "keyword_argument")
    )


def call_location(call_node):
    """1-based (line, col) of a constructor call."""
    return line_col(call_node)


def module_assignments(root):
    """Assignment nodes that are top-level statements of the module."""
    out = []
    for statement in root.children:
        if statement.type != "expression_statement":
            continue
        for inner in statement.children:
            if inner.type == "assignment":
                out.append(inner)
    return out


def vocab_expr_type_names(node, source: bytes, vocab_defs) -> set[str]:
    """Resolve a vocabulary expression to its set of type names.

    Handles a name referencing a defined vocabulary, an inline vocabulary({...})
    call, and a `a | b` merge (section, vocabulary merge); parenthesized too.
    """
    if node is None:
        return set()
    if node.type == "identifier":
        return set(vocab_defs.get(node_text(node, source), set()))
    if node.type == "call":
        return set(vocabulary_base_types(node, source).keys())
    if node.type == "binary_operator":
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        return vocab_expr_type_names(left, source, vocab_defs) | vocab_expr_type_names(
            right, source, vocab_defs
        )
    if node.type == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return vocab_expr_type_names(inner, source, vocab_defs)
    return set()


def build_vocabulary_definitions(root, source: bytes, aliases) -> dict:
    """{var_name: set(type_names)} for module-level vocabulary assignments and merges."""
    defs: dict = {}
    for assignment in module_assignments(root):
        left = assignment.child_by_field_name("left")
        right = assignment.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        defs[node_text(left, source)] = vocab_expr_type_names(right, source, defs)
    return defs


def _link_decorator_call(func_node, source: bytes, aliases):
    """The @link(...) decorator call node on a function, or None."""
    parent = func_node.parent
    if parent is None or parent.type != "decorated_definition":
        return None
    names, _modules = aliases
    for child in parent.children:
        if child.type != "decorator":
            continue
        expr = child.named_children[0] if child.named_children else None
        if expr is None or expr.type != "call":
            continue
        fn = expr.child_by_field_name("function")
        if fn is not None and fn.type == "identifier" and names.get(node_text(fn, source)) == "link":
            return expr
    return None


def function_name(func_node, source: bytes) -> str:
    name = func_node.child_by_field_name("name")
    return node_text(name, source) if name is not None else "<anonymous>"


def defined_function_names(root, source: bytes) -> set[str]:
    """Names of every function defined in the module."""
    return {
        function_name(node, source)
        for node in walk(root)
        if node.type == "function_definition"
    }


def extract_links(root, source: bytes, aliases, vocab_defs) -> dict:
    """{func_name: {accepts, emits, boundary, location}} for each @link function."""
    links: dict = {}
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = _link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        accepts = vocab_expr_type_names(kw.get("accepts"), source, vocab_defs)
        emits = vocab_expr_type_names(kw.get("emits"), source, vocab_defs)
        boundary = "boundary" in kw and node_text(kw["boundary"], source) == "True"
        links[function_name(node, source)] = {
            "accepts": accepts,
            "emits": emits,
            "boundary": boundary,
            "location": line_col(node),
        }
    return links


def extract_chains(root, source: bytes, aliases) -> list[dict]:
    """Each chain(link, ...) call as {name, links: [identifier names], location}."""
    chains: list[dict] = []
    for call in constructor_calls(root, source, aliases, "chain"):
        args = call.child_by_field_name("arguments")
        link_names = []
        if args is not None:
            for child in args.named_children:
                if child.type == "identifier":
                    link_names.append(node_text(child, source))
        chains.append(
            {
                "name": assigned_name(call, source),
                "links": link_names,
                "location": call_location(call),
            }
        )
    return chains


def keyword_args(call_node, source: bytes) -> dict:
    """{name: value_node} for a call's keyword arguments (e.g. state_machine(...))."""
    args = call_node.child_by_field_name("arguments")
    result: dict = {}
    if args is None:
        return result
    for child in args.named_children:
        if child.type != "keyword_argument":
            continue
        name = child.child_by_field_name("name")
        value = child.child_by_field_name("value")
        if name is not None and value is not None:
            result[node_text(name, source)] = value
    return result


def vocabulary_members(vocab_call_node, source: bytes) -> set[str]:
    """Union of all Set members across an inline vocabulary({...}) call's base types."""
    members: set[str] = set()
    for recognizer in vocabulary_base_types(vocab_call_node, source).values():
        if recognizer[0] == "set":
            members |= recognizer[1]
    return members


def string_list(node, source: bytes) -> list[str]:
    """String values of a list/tuple literal (e.g. terminal=[...])."""
    if node is None or node.type not in ("list", "tuple"):
        return []
    return [
        value
        for value in (string_value(element, source) for element in node.named_children)
        if value is not None
    ]


def transition_table(dict_node, source: bytes):
    """[(state, event, next_state)] from a transitions={(s, e): next, ...} literal."""
    out = []
    if dict_node is None or dict_node.type != "dictionary":
        return out
    for pair in dict_node.named_children:
        if pair.type != "pair":
            continue
        key = pair.child_by_field_name("key")
        value = pair.child_by_field_name("value")
        if key is None or value is None or key.type != "tuple":
            continue
        parts = [string_value(element, source) for element in key.named_children]
        if len(parts) != 2 or parts[0] is None or parts[1] is None:
            continue
        out.append((parts[0], parts[1], string_value(value, source)))
    return out


def extract_state_machines(root, source: bytes, aliases) -> list[dict]:
    """Each state_machine(...) call as a plain dict of its declared parts (section 7c)."""
    machines: list[dict] = []
    for call in constructor_calls(root, source, aliases, "state_machine"):
        kw = keyword_args(call, source)
        machines.append(
            {
                "name": assigned_name(call, source),
                "location": call_location(call),
                "states": vocabulary_members(kw["states"], source) if "states" in kw else set(),
                "events": vocabulary_members(kw["events"], source) if "events" in kw else set(),
                "initial": string_value(kw["initial"], source) if "initial" in kw else None,
                "terminal": set(string_list(kw.get("terminal"), source)),
                "transitions": transition_table(kw.get("transitions"), source),
            }
        )
    return machines
