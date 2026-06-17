"""Declaration graph: alias resolution + honest-framework call-site extraction
(spec §3.3, §3.4).

honest-check identifies calls to the framework constructors — `vocabulary()`,
`composed()`, `chain()`, `state_machine()`, `binding()` — regardless of how they
were imported, and reconstructs their literal arguments into structured records.
Construction-time rules (§4.1) operate on these records, not on raw ASTs.

Recognizer reprs are tagged tuples so rules dispatch on kind, not node type:
    ("set",         frozenset[str])
    ("insensitive", frozenset[str])
    ("predicate",   node)            # opaque; predicate-only checks are static-limited
"""
from __future__ import annotations

from typing import TypedDict

from honest_check.parse import find_by_type, node_text

_CONSTRUCTORS = frozenset({"vocabulary", "composed", "chain", "state_machine", "binding"})
_HONEST_MODULES = frozenset({"honest_type", "honest_check", "honest_state"})


# --- alias resolution (spec §3.3) ----------------------------------------


class Aliases(TypedDict):
    names: dict[str, str]     # local name -> canonical constructor name
    modules: frozenset[str]   # local names bound to an honest module (attr calls)


def resolve_aliases(root, src: bytes) -> Aliases:
    names: dict[str, str] = {}
    modules: set[str] = set()

    for imp in find_by_type(root, "import_from_statement"):
        module = imp.child_by_field_name("module_name")
        modname = node_text(module, src) if module is not None else ""
        if not any(m in modname for m in _HONEST_MODULES):
            continue
        for child in imp.named_children:
            if child is module:
                continue
            if child.type == "dotted_name":
                nm = node_text(child, src)
                if nm in _CONSTRUCTORS:
                    names[nm] = nm
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node is not None and alias_node is not None:
                    canon = node_text(name_node, src)
                    if canon in _CONSTRUCTORS:
                        names[node_text(alias_node, src)] = canon

    for imp in find_by_type(root, "import_statement"):
        for child in imp.named_children:
            if child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node is not None and alias_node is not None:
                    if node_text(name_node, src) in _HONEST_MODULES:
                        modules.add(node_text(alias_node, src))
            elif child.type == "dotted_name":
                if node_text(child, src) in _HONEST_MODULES:
                    modules.add(node_text(child, src))

    return {"names": names, "modules": frozenset(modules)}


def call_constructor(call, src: bytes, aliases: Aliases) -> str | None:
    """The canonical constructor a call invokes, or None if it is not one."""
    func = call.child_by_field_name("function")
    if func is None:
        return None
    if func.type == "identifier":
        return aliases["names"].get(node_text(func, src))
    if func.type == "attribute":
        obj = func.child_by_field_name("object")
        attr = func.child_by_field_name("attribute")
        if obj is not None and attr is not None:
            if node_text(obj, src) in aliases["modules"]:
                attrname = node_text(attr, src)
                if attrname in _CONSTRUCTORS:
                    return attrname
    return None


# --- literal extraction --------------------------------------------------


def _string_value(node, src: bytes) -> str | None:
    if node is None or node.type != "string":
        return None
    parts = [node_text(c, src) for c in node.children if c.type == "string_content"]
    return "".join(parts)


def _set_members(node, src: bytes) -> frozenset[str] | None:
    """Members of a `{...}` set literal, if all are strings."""
    if node is None or node.type != "set":
        return None
    members = []
    for elem in node.named_children:
        s = _string_value(elem, src)
        if s is None:
            return None     # heterogeneous / non-string set: not a plain Set recognizer
        members.append(s)
    return frozenset(members)


def _recognizer_repr(node, src: bytes):
    """Tag a recognizer value node: ('set'|'insensitive'|'ref'|'predicate', payload).

    A bare identifier (`'sender': user_id`) is a recognizer reference — tagged
    'ref' with its name, so two slots backed by the same reference are
    comparable (HC-P014). Inline lambdas / predicate() calls are 'predicate'
    (not statically comparable)."""
    if node is None:
        return ("predicate", node)
    if node.type == "identifier":
        return ("ref", node_text(node, src))
    if node.type == "set":
        members = _set_members(node, src)
        return ("set", members) if members is not None else ("predicate", node)
    if node.type == "lambda":
        return ("predicate", node)
    if node.type == "call":
        func = node.child_by_field_name("function")
        fname = node_text(func, src) if func is not None else ""
        tail = fname.split(".")[-1]
        args = node.child_by_field_name("arguments")
        first = args.named_children[0] if (args is not None and args.named_children) else None
        if tail == "set_recognizer":
            members = _set_members(first, src)
            return ("set", members) if members is not None else ("predicate", node)
        if tail == "insensitive":
            members = _set_members(first, src)
            return ("insensitive", members) if members is not None else ("predicate", node)
        # predicate(...) or any other call -> opaque predicate
        return ("predicate", node)
    return ("predicate", node)


def _dict_pairs(node, src: bytes):
    """(key_str, value_node) pairs of a `{...}` dictionary literal."""
    if node is None or node.type != "dictionary":
        return []
    pairs = []
    for pair in node.named_children:
        if pair.type != "pair":
            continue
        key = _string_value(pair.child_by_field_name("key"), src)
        value = pair.child_by_field_name("value")
        if key is not None:
            pairs.append((key, value))
    return pairs


def _positional_and_kwargs(call, src: bytes):
    """(positional_value_nodes, {kw_name: value_node}) of a call."""
    args = call.child_by_field_name("arguments")
    positional = []
    kwargs = {}
    if args is None:
        return positional, kwargs
    for child in args.named_children:
        if child.type == "keyword_argument":
            name = child.child_by_field_name("name")
            value = child.child_by_field_name("value")
            if name is not None:
                kwargs[node_text(name, src)] = value
        else:
            positional.append(child)
    return positional, kwargs


# --- structured records --------------------------------------------------


def extract_vocabulary(call, src: bytes) -> dict:
    positional, kwargs = _positional_and_kwargs(call, src)
    base_node = positional[0] if positional else kwargs.get("base_types")
    base_types = {
        name: _recognizer_repr(value, src)
        for name, value in _dict_pairs(base_node, src)
    }
    composed_node = kwargs.get("composed_types")
    composed_types = []
    if composed_node is not None and composed_node.type == "list":
        for elem in composed_node.named_children:
            if elem.type == "call":
                composed_types.append(extract_composed(elem, src))
    return {"base_types": base_types, "composed_types": composed_types, "node": call}


def extract_composed(call, src: bytes) -> dict:
    positional, kwargs = _positional_and_kwargs(call, src)
    name = _string_value(positional[0], src) if positional else None
    requires_node = kwargs.get("requires")
    requires = {k: _string_value(v, src) for k, v in _dict_pairs(requires_node, src)}
    captures_node = kwargs.get("captures")
    # captures may be a bare string or a maybe("type") call; take the tail string.
    captures = _string_value(captures_node, src)
    if captures is None and captures_node is not None and captures_node.type == "call":
        cpos, _ = _positional_and_kwargs(captures_node, src)
        captures = _string_value(cpos[0], src) if cpos else None
    return {"name": name, "requires": requires, "captures": captures, "node": call}


def extract_chain(call, src: bytes) -> dict:
    positional, _ = _positional_and_kwargs(call, src)
    return {"link_count": len(positional), "node": call}


def _name_set(node, src: bytes) -> frozenset[str]:
    """State/event names from a `{...}`/`[...]` literal or a `vocabulary(...)`
    call (union of its Set members)."""
    if node is None:
        return frozenset()
    if node.type in ("set", "list"):
        return frozenset(
            s for s in (_string_value(e, src) for e in node.named_children)
            if s is not None
        )
    if node.type == "call":
        func = node.child_by_field_name("function")
        tail = node_text(func, src).split(".")[-1] if func is not None else ""
        if tail == "vocabulary":
            voc = extract_vocabulary(node, src)
            out: set[str] = set()
            for kind, payload in voc["base_types"].values():
                if kind in ("set", "insensitive") and payload:
                    out |= set(payload)
            return frozenset(out)
    return frozenset()


def _tuple_strings(node, src: bytes):
    """The two string members of a `(state, event)` tuple key, or None."""
    if node is None or node.type != "tuple":
        return None
    parts = [_string_value(c, src) for c in node.named_children]
    if len(parts) == 2 and all(p is not None for p in parts):
        return (parts[0], parts[1])
    return None


def extract_state_machine(call, src: bytes) -> dict:
    _, kwargs = _positional_and_kwargs(call, src)
    states = _name_set(kwargs.get("states"), src)
    events = _name_set(kwargs.get("events"), src)
    initial = _string_value(kwargs.get("initial"), src)
    terminal = _name_set(kwargs.get("terminal"), src)
    state_fields = _name_set(kwargs.get("state_fields"), src)
    transitions = []
    trans_node = kwargs.get("transitions")
    if trans_node is not None and trans_node.type == "dictionary":
        for pair in trans_node.named_children:
            if pair.type != "pair":
                continue
            key = _tuple_strings(pair.child_by_field_name("key"), src)
            if key is None:
                continue
            value = pair.child_by_field_name("value")
            transitions.append({
                "state": key[0], "event": key[1],
                "target": _string_value(value, src),   # None when the value is a function
                "value": value,
            })
    return {
        "states": states, "events": events, "initial": initial,
        "terminal": terminal, "state_fields": state_fields,
        "transitions": transitions, "node": call,
    }


def extract_binding(call, src: bytes) -> dict:
    positional, kwargs = _positional_and_kwargs(call, src)
    node = positional[0] if positional else kwargs.get("rules")
    entries: dict = {}
    for type_name, value in _dict_pairs(node, src):
        slot = _string_value(value, src)
        if slot is None and value is not None and value.type == "call":
            cpos, _ = _positional_and_kwargs(value, src)   # maybe("slot")
            slot = _string_value(cpos[0], src) if cpos else None
        entries[type_name] = slot
    return {"entries": entries, "node": call}


def find_constructor_calls(root, src: bytes):
    """Yield (constructor_name, call_node) for every resolved honest call."""
    aliases = resolve_aliases(root, src)
    for call in find_by_type(root, "call"):
        ctor = call_constructor(call, src, aliases)
        if ctor is not None:
            yield ctor, call


def build_definition_map(root, src: bytes) -> dict:
    """`NAME` -> (constructor, record) for `NAME = vocabulary(...)/binding(...)`."""
    aliases = resolve_aliases(root, src)
    out: dict = {}
    for assign in find_by_type(root, "assignment"):
        left = assign.child_by_field_name("left")
        right = assign.child_by_field_name("right")
        if (left is None or left.type != "identifier"
                or right is None or right.type != "call"):
            continue
        ctor = call_constructor(right, src, aliases)
        if ctor == "vocabulary":
            out[node_text(left, src)] = ("vocabulary", extract_vocabulary(right, src))
        elif ctor == "binding":
            out[node_text(left, src)] = ("binding", extract_binding(right, src))
    return out


def _resolve_record(arg, kind: str, src: bytes, defs: dict, aliases):
    if arg is None:
        return None
    if arg.type == "identifier":
        entry = defs.get(node_text(arg, src))
        return entry[1] if entry is not None and entry[0] == kind else None
    if arg.type == "call":
        ctor = call_constructor(arg, src, aliases)
        if ctor == "vocabulary" and kind == "vocabulary":
            return extract_vocabulary(arg, src)
        if ctor == "binding" and kind == "binding":
            return extract_binding(arg, src)
    return None


def find_classify_pairings(root, src: bytes):
    """Yield (vocabulary_record, binding_record|None) for each classify() call,
    pairing a vocabulary with its binding via call arguments."""
    aliases = resolve_aliases(root, src)
    defs = build_definition_map(root, src)
    out = []
    for call in find_by_type(root, "call"):
        func = call.child_by_field_name("function")
        if func is None or func.type not in ("identifier", "attribute"):
            continue
        if node_text(func, src).split(".")[-1] != "classify":
            continue
        positional, kwargs = _positional_and_kwargs(call, src)
        vocab_arg = positional[1] if len(positional) > 1 else kwargs.get("vocabulary")
        binding_arg = positional[2] if len(positional) > 2 else kwargs.get("binding")
        vocab = _resolve_record(vocab_arg, "vocabulary", src, defs, aliases)
        if vocab is not None:
            out.append((vocab, _resolve_record(binding_arg, "binding", src, defs, aliases)))
    return out


# --- @link metadata + chain link resolution (spec §4.4, §10) --------------


def _link_decorator_call(fn, src: bytes):
    """If fn is decorated `@link` / `@link(...)`, return the call node (or the
    bare decorator expr), else None."""
    parent = fn.parent
    if parent is None or parent.type != "decorated_definition":
        return None
    for child in parent.children:
        if child.type != "decorator":
            continue
        expr = child.named_children[0] if child.named_children else None
        if expr is None:
            continue
        if expr.type == "identifier" and node_text(expr, src) == "link":
            return expr
        if expr.type == "call":
            func = expr.child_by_field_name("function")
            if func is not None and _dotted_tail(func, src) == "link":
                return expr
    return None


def _dotted_tail(node, src: bytes) -> str:
    if node is None:
        return ""
    if node.type == "identifier":
        return node_text(node, src)
    if node.type == "attribute":
        attr = node.child_by_field_name("attribute")
        return node_text(attr, src) if attr is not None else ""
    return ""


def _vocab_typenames(node, src: bytes, defs: dict, aliases) -> set:
    """Type names of a vocab expression: a name, an inline vocabulary() call, or
    a `v | w` merge."""
    if node is None:
        return set()
    if node.type == "identifier":
        entry = defs.get(node_text(node, src))
        if entry is not None and entry[0] == "vocabulary":
            v = entry[1]
            return set(v["base_types"]) | {c["name"] for c in v["composed_types"]}
        return set()
    if node.type == "call":
        if call_constructor(node, src, aliases) == "vocabulary":
            v = extract_vocabulary(node, src)
            return set(v["base_types"]) | {c["name"] for c in v["composed_types"]}
        return set()
    if node.type == "binary_operator":
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        return (_vocab_typenames(left, src, defs, aliases)
                | _vocab_typenames(right, src, defs, aliases))
    return set()


def link_definitions(root, src: bytes) -> dict:
    """fn_name -> {accepts, emits, boundary, node} for every @link function."""
    aliases = resolve_aliases(root, src)
    defs = build_definition_map(root, src)
    out: dict = {}
    for fn in find_by_type(root, "function_definition"):
        deco = _link_decorator_call(fn, src)
        if deco is None:
            continue
        name_node = fn.child_by_field_name("name")
        name = node_text(name_node, src) if name_node is not None else ""
        accepts: set = set()
        emits: set = set()
        boundary = False
        authorizes = False
        if deco.type == "call":
            _, kwargs = _positional_and_kwargs(deco, src)
            accepts = _vocab_typenames(kwargs.get("accepts"), src, defs, aliases)
            emits = _vocab_typenames(kwargs.get("emits"), src, defs, aliases)
            bv = kwargs.get("boundary")
            boundary = bv is not None and bv.type == "true"
            av = kwargs.get("authorizes")
            authorizes = av is not None and av.type == "true"
        out[name] = {"accepts": accepts, "emits": emits, "boundary": boundary,
                     "authorizes": authorizes, "node": fn}
    return out


def local_function_names(root, src: bytes) -> set:
    names = set()
    for fn in find_by_type(root, "function_definition"):
        name_node = fn.child_by_field_name("name")
        if name_node is not None:
            names.add(node_text(name_node, src))
    return names


def chain_link_args(root, src: bytes):
    """For each chain() call: (call_node, [arg_name_or_None, ...]) positional."""
    out = []
    for ctor, call in find_constructor_calls(root, src):
        if ctor != "chain":
            continue
        positional, _ = _positional_and_kwargs(call, src)
        names = [node_text(a, src) if a.type == "identifier" else None for a in positional]
        out.append((call, names))
    return out


# --- roles + static call graph (spec §4.2 HC-R001/OR001/OR003) ------------

_ROLES = frozenset({"link", "recognizer", "boundary", "helper", "orchestrator"})


def function_role(fn, src: bytes) -> str | None:
    """The declared role of a function from its decorators, or None."""
    parent = fn.parent
    if parent is None or parent.type != "decorated_definition":
        return None
    for child in parent.children:
        if child.type != "decorator":
            continue
        expr = child.named_children[0] if child.named_children else None
        if expr is None:
            continue
        if expr.type == "identifier":
            tail = node_text(expr, src)
        elif expr.type == "call":
            tail = _dotted_tail(expr.child_by_field_name("function"), src)
        else:
            tail = ""
        if tail in _ROLES:
            return tail
    return None


def _fn_name(fn, src: bytes) -> str:
    name_node = fn.child_by_field_name("name")
    return node_text(name_node, src) if name_node is not None else ""


def role_map(root, src: bytes):
    """(roles {name: role}, nodes {name: fn_node})."""
    roles: dict = {}
    nodes: dict = {}
    for fn in find_by_type(root, "function_definition"):
        name = _fn_name(fn, src)
        nodes[name] = fn
        role = function_role(fn, src)
        if role is not None:
            roles[name] = role
    return roles, nodes


def call_graph(root, src: bytes) -> dict:
    """fn_name -> set of local function names it calls (over-approximate:
    includes calls made by nested functions, which is safe for reachability)."""
    local = local_function_names(root, src)
    graph: dict = {}
    for fn in find_by_type(root, "function_definition"):
        name = _fn_name(fn, src)
        called = graph.setdefault(name, set())
        for call in find_by_type(fn, "call"):
            func = call.child_by_field_name("function")
            if func is not None and func.type == "identifier":
                callee = node_text(func, src)
                if callee in local:
                    called.add(callee)
    return graph


def call_sequence(fn, src: bytes) -> list:
    """Ordered tail-names of calls directly in a function (not nested)."""
    body = fn.child_by_field_name("body")
    seq: list = []
    stack = list(body.children)[::-1] if body is not None else []
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            continue
        if node.type == "call":
            seq.append(_dotted_tail(node.child_by_field_name("function"), src))
        stack.extend(node.children[::-1])
    return seq
