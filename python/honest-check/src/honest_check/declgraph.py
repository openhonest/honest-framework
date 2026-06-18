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
