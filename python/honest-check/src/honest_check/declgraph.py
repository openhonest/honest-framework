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

from honest_parse import line_col, node_text, walk

_HONEST_TYPE_NAMES = frozenset(
    {
        "vocabulary", "binding", "composed", "chain", "link", "predicate",
        "state_machine", "classify",
    }
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
                if child == module:
                    continue
                if child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    alias = child.child_by_field_name("alias")
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
        if fn.type == "identifier" and names.get(node_text(fn, source)) == canonical:
            out.append(node)
        if fn.type == "attribute":
            obj = fn.child_by_field_name("object")
            attr = fn.child_by_field_name("attribute")
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
    """The base-types dict of a vocabulary call: positional, or a base_types= keyword."""
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
        type_name = string_value(key, source)
        if type_name is None:
            continue
        base_types[type_name] = _recognizer(value, source)
    return base_types


def _parse_composed(call_node, source: bytes) -> dict:
    """A composed(name, requires={...}, captures=...) call -> its record (section 7)."""
    kw = keyword_args(call_node, source)
    name = None
    args = call_node.child_by_field_name("arguments")
    if args is not None:
        for child in args.named_children:
            if child.type == "string":
                name = string_value(child, source)
                break
    if name is None and "name" in kw:
        name = string_value(kw["name"], source)

    requires: set[str] = set()
    requires_node = kw.get("requires")
    if requires_node is not None and requires_node.type == "dictionary":
        for pair in requires_node.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            type_name = string_value(key, source) if key is not None else None
            if type_name is not None:
                requires.add(type_name)

    captures = None
    captures_node = kw.get("captures")
    if captures_node is not None:
        if captures_node.type == "call":  # maybe("integer") -> unwrap
            inner = captures_node.child_by_field_name("arguments")
            for child in inner.named_children:
                if child.type == "string":
                    captures = string_value(child, source)
                    break
        else:
            captures = string_value(captures_node, source)

    return {"name": name, "requires": requires, "captures": captures, "location": line_col(call_node)}


def extract_composed_types(vocab_call, source: bytes, aliases) -> list[dict]:
    """Composed records from a vocabulary call's composed_types=[composed(...)] list."""
    names, _modules = aliases
    kw = keyword_args(vocab_call, source)
    composed_list = kw.get("composed_types")
    out: list[dict] = []
    if composed_list is None or composed_list.type != "list":
        return out
    for element in composed_list.named_children:
        if element.type != "call":
            continue
        fn = element.child_by_field_name("function")
        if fn is None or fn.type != "identifier" or names.get(node_text(fn, source)) != "composed":
            continue
        out.append(_parse_composed(element, source))
    return out


def extract_bindings(root, source: bytes, aliases) -> dict:
    """{var_name: {'table': {type: slot}, 'location': (line, col)}} for binding() calls."""
    out: dict = {}
    for call in constructor_calls(root, source, aliases, "binding"):
        name = assigned_name(call, source)
        if name is None:
            continue
        table: dict = {}
        dict_node = _dictionary_arg(call)
        if dict_node is not None:
            for pair in dict_node.named_children:
                if pair.type != "pair":
                    continue
                key = pair.child_by_field_name("key")
                value = pair.child_by_field_name("value")
                type_name = string_value(key, source) if key is not None else None
                slot_name = string_value(value, source) if value is not None else None
                if type_name is not None and slot_name is not None:
                    table[type_name] = slot_name
        out[name] = {"table": table, "location": call_location(call)}
    return out


def extract_vocabularies(root, source: bytes, aliases) -> dict:
    """{var_name: {'base': {type: recognizer}, 'composed': [records], 'composed_names': set,
    'location': (line, col)}} for vocabulary() assignments."""
    out: dict = {}
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        name = assigned_name(call, source)
        if name is None:
            continue
        composed = extract_composed_types(call, source, aliases)
        out[name] = {
            "base": vocabulary_base_types(call, source),
            "composed": composed,
            "composed_names": {record["name"] for record in composed if record["name"]},
            "location": call_location(call),
        }
    return out


def vocab_binding_pairings(root, source: bytes, aliases):
    """[(vocab_var, binding_var)] paired via @link(accepts=, binds=) or classify(vocab=, bind=)."""
    pairs = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        vocab = kw.get("accepts")
        binding = kw.get("binds")
        if vocab is not None and vocab.type == "identifier" and binding is not None and binding.type == "identifier":
            pairs.append((node_text(vocab, source), node_text(binding, source)))

    for call in constructor_calls(root, source, aliases, "classify"):
        kw = keyword_args(call, source)
        vocab = kw.get("vocab")
        binding = kw.get("bind")
        if vocab is None or binding is None:
            args = call.child_by_field_name("arguments")
            positional = [
                child
                for child in (args.named_children if args is not None else [])
                if child.type != "keyword_argument"
            ]
            if vocab is None and len(positional) >= 2:
                vocab = positional[1]
            if binding is None and len(positional) >= 3:
                binding = positional[2]
        if vocab is not None and vocab.type == "identifier" and binding is not None and binding.type == "identifier":
            pairs.append((node_text(vocab, source), node_text(binding, source)))
    return pairs


def _calls_by_name(root, source: bytes, callee: str):
    """All call nodes whose callee is the bare identifier `callee`."""
    out = []
    for node in walk(root):
        if node.type != "call":
            continue
        fn = node.child_by_field_name("function")
        if fn is not None and fn.type == "identifier" and node_text(fn, source) == callee:
            out.append(node)
    return out


def authorizing_links(root, source: bytes, aliases):
    """[(func_name, func_node)] for functions decorated @link(authorizes=True)."""
    out = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        if "authorizes" in kw and node_text(kw["authorizes"], source) == "True":
            out.append((function_name(node, source), node))
    return out


def _derivation_signature(deriv_node, source: bytes) -> str:
    """The derivation name in GuardExpressionTemplate.lookup('name', ...); '' for literal."""
    if deriv_node.type != "call":
        return ""
    fn = deriv_node.child_by_field_name("function")
    method = node_text(fn, source).split(".")[-1] if fn is not None else ""
    if method != "lookup":
        return ""  # .literal(...) etc. — no derivation expression to reference
    args = deriv_node.child_by_field_name("arguments")
    for child in args.named_children:
        if child.type == "string":
            return string_value(child, source) or ""
    return ""


def registered_provider_signature(root, source: bytes, aliases):
    """The registered provider's derivation signature.

    Returns None if no provider is registered; '' if registered with a literal
    (no-auth) derivation; otherwise the derivation name authorizing links must
    reference (e.g. 'session_actor'). Auth is a wrapper over a 3rd-party provider:
    register_auth_provider(p) where p = AuthProvider(derivation_expression=...).
    """
    registrations = _calls_by_name(root, source, "register_auth_provider")
    if not registrations:
        return None
    provider_vars: set[str] = set()
    for call in registrations:
        args = call.child_by_field_name("arguments")
        for child in args.named_children:
            if child.type == "identifier":
                provider_vars.add(node_text(child, source))
    for assignment in module_assignments(root):
        left = assignment.child_by_field_name("left")
        right = assignment.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier" or right.type != "call":
            continue
        if node_text(left, source) not in provider_vars:
            continue
        fn = right.child_by_field_name("function")
        if fn is None or node_text(fn, source).split(".")[-1] != "AuthProvider":
            continue
        deriv = keyword_args(right, source).get("derivation_expression")
        return _derivation_signature(deriv, source) if deriv is not None else ""
    return ""  # registered, but provider definition not inline


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


def link_decorator_call(func_node, source: bytes, aliases):
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


# The declared function roles auto-generation exercises (sections HC-R001, HC-OR001).
_ROLE_DECORATORS = frozenset({"link", "recognizer", "boundary", "helper", "orchestrator"})


def function_role(func_node, source: bytes):
    """The declared role of a function from its decorators, or None."""
    parent = func_node.parent
    if parent is None or parent.type != "decorated_definition":
        return None
    for child in parent.children:
        if child.type != "decorator":
            continue
        expr = child.named_children[0]
        if expr.type == "identifier":
            name = node_text(expr, source)
        elif expr.type == "call":
            fn = expr.child_by_field_name("function")
            name = node_text(fn, source) if fn is not None else ""
        else:
            name = ""
        role = name.split(".")[-1]
        if role in _ROLE_DECORATORS:
            return role
    return None


def function_calls(func_node, source: bytes) -> set[str]:
    """Names of functions called (by bare identifier) inside a function body."""
    calls: set[str] = set()
    body = func_node.child_by_field_name("body")
    if body is None:
        return calls
    for node in walk(body):
        if node.type != "call":
            continue
        fn = node.child_by_field_name("function")
        if fn is not None and fn.type == "identifier":
            calls.add(node_text(fn, source))
    return calls


def functions_by_name(root, source: bytes) -> dict:
    """{function_name: function_definition node} for the module."""
    return {
        function_name(node, source): node
        for node in walk(root)
        if node.type == "function_definition"
    }


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
        decorator = link_decorator_call(node, source, aliases)
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


def _route_key(key_node, source: bytes):
    """The (method, path) of a route-map key, or None when the key is not a two-string tuple."""
    if key_node.type != "tuple":
        return None
    strings = [child for child in key_node.named_children if child.type == "string"]
    if len(strings) != 2:
        return None
    return (string_value(strings[0], source), string_value(strings[1], source))


def extract_routes(root, source: bytes) -> list:
    """The declared route map (honest-page §9) as a list of {method, path, chain}: each ROUTES entry's
    (method, path) string-tuple key paired with the identifier naming the chain that route runs. Pure —
    the declaration is read by parsing, never by running it. An assignment that is not a ROUTES
    dictionary, and any entry whose key is not a two-string tuple or whose value is not a chain
    identifier (or is a splat), is skipped."""
    routes = []
    for assignment in module_assignments(root):
        left = assignment.child_by_field_name("left")
        right = assignment.child_by_field_name("right")
        if node_text(left, source) != "ROUTES" or right.type != "dictionary":
            continue
        for pair in right.named_children:
            if pair.type != "pair":
                continue
            key = _route_key(pair.child_by_field_name("key"), source)
            value = pair.child_by_field_name("value")
            if key is not None and value.type == "identifier":
                routes.append({"method": key[0], "path": key[1], "chain": node_text(value, source)})
    return routes


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
