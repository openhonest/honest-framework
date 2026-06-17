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
    """Tag a recognizer value node: ('set'|'insensitive'|'predicate', payload)."""
    if node is None:
        return ("predicate", node)
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


def find_constructor_calls(root, src: bytes):
    """Yield (constructor_name, call_node) for every resolved honest call."""
    aliases = resolve_aliases(root, src)
    for call in find_by_type(root, "call"):
        ctor = call_constructor(call, src, aliases)
        if ctor is not None:
            yield ctor, call
