"""The §3.3 alias resolver and §3.4 declaration-graph extractor.

honest-check does not read the application's framework objects by running them;
it reads the construction call sites in the source and extracts their literal
arguments into a declaration graph (section 3.4). The construction-time rules
(HC003, HC006, HC007, HC011, HC-SM01/02/05) read this graph, never the raw AST
(section 3.4: "Rules operate on this graph, not on raw ASTs").

Two steps, both pure, both Python-specific here (the node types are
tree-sitter-python's; other languages' extractors are their own rows, a tracked
follow-on). First `resolve_aliases` walks the imports and records how the four
framework constructors are named locally (section 3.3). Then `build_graph` walks
the calls, recognizes a construction site through that alias map, and dispatches
on the resolved constructor name through a table to the matching extractor.

A graph def carries the construction call node's 1-based (line, col) so a rule
can stamp each Diagnostic's source_location as file:line:col without re-walking
the tree.
"""

from typing import TypedDict

from honest_parse import line_col, walk


# --- graph shapes (section 3.4), TypedDicts, the only class form allowed ------

class Recognizer(TypedDict):
    kind: str          # "set" or "predicate"
    members: list[str]  # the Set's values; empty for a predicate


class ComposedDef(TypedDict):
    name: str
    requires: list[str]
    captures: str
    line: int
    col: int


class VocabularyDef(TypedDict):
    name: str
    base_types: dict[str, Recognizer]
    composed_types: list[ComposedDef]
    line: int
    col: int


class ChainDef(TypedDict):
    name: str
    link_count: int
    line: int
    col: int


class StateMachineDef(TypedDict):
    name: str
    states: list[str]
    events: list[str]
    transitions: list[tuple[str, str]]
    initial: str
    line: int
    col: int


class DeclarationGraph(TypedDict):
    vocabularies: list[VocabularyDef]
    chains: list[ChainDef]
    state_machines: list[StateMachineDef]


# The four honest-framework constructors the extractor recognizes. composed() is
# a constructor too, but it is never a top-level graph node: it appears only
# inside a vocabulary()'s composed_types, so it is extracted there (HC006 reads
# vocabulary.composed_types) and carries no row in the top-level dispatch table.
_CONSTRUCTORS = frozenset({"chain", "vocabulary", "composed", "state_machine"})


def _empty_graph() -> DeclarationGraph:
    return {"vocabularies": [], "chains": [], "state_machines": []}


# --- node helpers -------------------------------------------------------------

def _string_value(string_node) -> str:
    """The content of a tree-sitter string node, without its quotes. The empty
    string for a string with no content node (an empty literal)."""
    for child in string_node.named_children:
        if child.type == "string_content":
            return child.text.decode("utf-8")
    return ""


def _set_members(set_node) -> list[str]:
    """The string values of a set literal recognizer."""
    return [
        _string_value(child)
        for child in set_node.named_children
        if child.type == "string"
    ]


def _classify_recognizer(value_node) -> Recognizer:
    """A base-declaration value is a Set recognizer when it is a set literal and
    a predicate recognizer otherwise (a lambda, a name, a call). honest-check
    never runs the predicate (section 4.1); classifying it by node shape is all
    the static read needs."""
    if value_node.type == "set":
        return {"kind": "set", "members": _set_members(value_node)}
    return {"kind": "predicate", "members": []}


def _dict_pairs(dict_node):
    """(key_node, value_node) for each pair in a dictionary literal."""
    pairs = []
    for pair in dict_node.named_children:
        if pair.type == "pair" and len(pair.named_children) >= 2:
            pairs.append((pair.named_children[0], pair.named_children[1]))
    return pairs


def _list_items(list_node):
    """The element nodes of a list literal."""
    return list(list_node.named_children)


def _positional_args(call_node):
    """The positional argument nodes of a call, keyword arguments dropped."""
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return []
    return [c for c in args.named_children if c.type != "keyword_argument"]


def _keyword_arg(call_node, key: str):
    """The value node of a call's `key=...` keyword argument, or None."""
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return None
    for child in args.named_children:
        if child.type == "keyword_argument":
            parts = child.named_children
            if len(parts) >= 2 and parts[0].text.decode("utf-8") == key:
                return parts[1]
    return None


def _at(i, nodes):
    """The i-th node of a list, or None when the source did not supply it. The
    application source is untrusted, so a construction call may be written with
    fewer arguments than the constructor takes; that is boundary tolerance, not
    interior distrust."""
    return nodes[i] if 0 <= i < len(nodes) else None


def _assignment_name(call_node) -> str:
    """The name a construction call is assigned to, for the diagnostic message.
    '<anonymous>' when the call is not the right-hand side of a plain
    assignment. The suite compares only (rule, severity, line), so the name is
    for the human sentence, never for the match."""
    parent = call_node.parent
    if parent is not None and parent.type == "assignment":
        first = parent.named_children[0] if parent.named_children else None
        if first is not None and first.type == "identifier":
            return first.text.decode("utf-8")
    return "<anonymous>"


# --- alias resolution (section 3.3) -------------------------------------------

def resolve_aliases(root) -> dict[str, str]:
    """Map each locally-bound name back to the framework name it imports
    (section 3.3). `from honest_type import vocabulary as v` records v -> vocabulary;
    `import honest_type as ht` records 'ht.*' -> 'honest_type.*' so an attribute
    call ht.chain() resolves. A plain `import chain` needs no row: a bare call
    chain() already matches the framework name directly."""
    aliases: dict[str, str] = {}
    for node in walk(root):
        if node.type == "import_from_statement":
            for child in node.named_children:
                if child.type == "aliased_import":
                    aliases.update(_aliased_import_pair(child))
        elif node.type == "import_statement":
            for child in node.named_children:
                if child.type == "aliased_import":
                    aliases.update(_module_alias_pair(child))
    return aliases


def _aliased_import_pair(aliased) -> dict[str, str]:
    """{alias: imported_name} for `X as Y` inside a from-import."""
    parts = aliased.named_children
    if len(parts) >= 2:
        imported = parts[0].text.decode("utf-8")
        alias = parts[1].text.decode("utf-8")
        return {alias: imported}
    return {}


def _module_alias_pair(aliased) -> dict[str, str]:
    """{alias.*: module.*} for `import module as alias`."""
    parts = aliased.named_children
    if len(parts) >= 2:
        module = parts[0].text.decode("utf-8")
        alias = parts[1].text.decode("utf-8")
        return {f"{alias}.*": f"{module}.*"}
    return {}


def _resolve_call_name(func_node, aliases: dict[str, str]):
    """The framework name a call's function resolves to, or None when the call
    is not a framework call. An identifier resolves through the alias map (or is
    itself the name); an attribute obj.attr resolves when obj is a module alias
    (section 3.3's is_honest_call, generalized over the four constructor names)."""
    if func_node.type == "identifier":
        raw = func_node.text.decode("utf-8")
        return aliases.get(raw, raw)
    if func_node.type == "attribute":
        obj = func_node.child_by_field_name("object")
        attr = func_node.child_by_field_name("attribute")
        if obj is not None and attr is not None and obj.type == "identifier":
            if f"{obj.text.decode('utf-8')}.*" in aliases:
                return attr.text.decode("utf-8")
    return None


# --- per-constructor extraction -----------------------------------------------

def _extract_chain(call_node, aliases) -> ChainDef:
    line, col = line_col(call_node)
    return {
        "name": _assignment_name(call_node),
        "link_count": len(_positional_args(call_node)),
        "line": line,
        "col": col,
    }


def _extract_vocabulary(call_node, aliases) -> VocabularyDef:
    line, col = line_col(call_node)
    positional = _positional_args(call_node)
    base_types: dict[str, Recognizer] = {}
    base_node = _at(0, positional)
    if base_node is not None and base_node.type == "dictionary":
        for key_node, value_node in _dict_pairs(base_node):
            base_types[_string_value(key_node)] = _classify_recognizer(value_node)
    composed_node = _keyword_arg(call_node, "composed_types") or _at(1, positional)
    composed_types: list[ComposedDef] = []
    if composed_node is not None and composed_node.type == "list":
        for item in _list_items(composed_node):
            if item.type == "call":
                func = item.child_by_field_name("function")
                if func is not None and _resolve_call_name(func, aliases) == "composed":
                    composed_types.append(_extract_composed(item, aliases))
    return {
        "name": _assignment_name(call_node),
        "base_types": base_types,
        "composed_types": composed_types,
        "line": line,
        "col": col,
    }


def _extract_composed(call_node, aliases) -> ComposedDef:
    line, col = line_col(call_node)
    positional = _positional_args(call_node)
    name_node = _at(0, positional)
    requires_node = _at(1, positional)
    captures_node = _at(2, positional)
    requires: list[str] = []
    if requires_node is not None and requires_node.type == "dictionary":
        requires = [_string_value(k) for k, _ in _dict_pairs(requires_node)]
    captures = ""
    if captures_node is not None:
        captures = (
            _string_value(captures_node)
            if captures_node.type == "string"
            else captures_node.text.decode("utf-8")
        )
    return {
        "name": _string_value(name_node) if name_node is not None else "<anonymous>",
        "requires": requires,
        "captures": captures,
        "line": line,
        "col": col,
    }


def _extract_state_machine(call_node, aliases) -> StateMachineDef:
    line, col = line_col(call_node)
    positional = _positional_args(call_node)
    states_node = _at(0, positional)
    events_node = _at(1, positional)
    transitions_node = _at(2, positional)
    initial_node = _at(3, positional)
    states = _string_list(states_node)
    events = _string_list(events_node)
    transitions: list[tuple[str, str]] = []
    if transitions_node is not None and transitions_node.type == "dictionary":
        for key_node, _value in _dict_pairs(transitions_node):
            if key_node.type == "tuple":
                members = [
                    _string_value(c)
                    for c in key_node.named_children
                    if c.type == "string"
                ]
                if len(members) >= 2:
                    transitions.append((members[0], members[1]))
    initial = ""
    if initial_node is not None and initial_node.type == "string":
        initial = _string_value(initial_node)
    return {
        "name": _assignment_name(call_node),
        "states": states,
        "events": events,
        "transitions": transitions,
        "initial": initial,
        "line": line,
        "col": col,
    }


def _string_list(list_node) -> list[str]:
    """The string values of a list literal, or [] when the node is absent or not
    a list."""
    if list_node is None or list_node.type != "list":
        return []
    return [
        _string_value(item)
        for item in list_node.named_children
        if item.type == "string"
    ]


# The construction-site dispatch table: resolved constructor name -> extractor,
# paired with the graph bucket the result joins. composed() is deliberately not a
# row here (it is extracted inside _extract_vocabulary); a call whose resolved
# name is not a key is simply not a construction site, which is the common case
# for arbitrary source, so the membership guard is a recognizer, not a fault.
_EXTRACTORS = {
    "chain": (_extract_chain, "chains"),
    "vocabulary": (_extract_vocabulary, "vocabularies"),
    "state_machine": (_extract_state_machine, "state_machines"),
}


def _extract_python_graph(root, source: str) -> DeclarationGraph:
    aliases = resolve_aliases(root)
    graph = _empty_graph()
    for node in walk(root):
        if node.type != "call":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        name = _resolve_call_name(func, aliases)
        if name not in _EXTRACTORS:
            continue
        extractor, bucket = _EXTRACTORS[name]
        graph[bucket].append(extractor(node, aliases))
    return graph


# The extractor is grammar-specific: these node types are tree-sitter-python's.
# Keyed by language with an explicit no-match row returning the empty graph, so a
# recognized non-Python file contributes no construction graph this run (its
# extractor is a tracked follow-on) rather than being read under Python's node
# types.
_GRAPH_EXTRACTOR_BY_LANGUAGE = {
    "python": _extract_python_graph,
}


def build_graph(root, language: str, source: str) -> DeclarationGraph:
    """The §3.4 declaration graph for one parsed source. The empty graph for a
    language with no built extractor this run."""
    if language not in _GRAPH_EXTRACTOR_BY_LANGUAGE:
        return _empty_graph()
    return _GRAPH_EXTRACTOR_BY_LANGUAGE[language](root, source)
