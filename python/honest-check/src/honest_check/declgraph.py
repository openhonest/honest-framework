"""The declaration-graph extractors honest-check shares with honest-test (spec §3.5).

resolve_aliases, extract_chains and extract_state_machines are the public counterparts of
the alias map and declaration graph check_source builds internally (§3.3, §3.4), written
once here so the two tools never derive "what is a chain" independently and drift. honest-test
parses each file once with honest-parse and hands the root node and the source bytes in; the
two extractors also take the alias map resolve_aliases returned for that same file. Each
returns its result as data and raises nothing: a construct that cannot be recognized is
absent from the returned list, never an error.
"""

from honest_parse import walk

# The honest-framework construction names an extractor recognizes. A call whose function
# identifier resolves — directly, or through the alias map — to one of these names is that
# construction (§3.3, §3.4).
_CHAIN = "chain"
_STATE_MACHINE = "state_machine"
_CONSTRUCTORS = frozenset({_CHAIN, _STATE_MACHINE})


def resolve_aliases(root, source):
    """The import-alias resolver of §3.3, exposed for honest-test (§3.5). Reads every
    `from honest_type import ...` statement off the parsed tree and returns the map from
    each local name the source bound a honest_type import to, to that import's canonical
    framework name: a plain import maps a name to itself, an aliased import maps the local
    alias to the canonical name. Imports from any other module contribute nothing, and a
    file that imports nothing from honest_type yields the empty map."""
    aliases = {}
    for node in walk(root):
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


def extract_chains(root, source, aliases):
    """The chain recognizer of the §3.4 declaration graph, exposed for honest-test (§3.5).
    Finds every module-level assignment whose right side is a `chain(...)` call — recognized
    through the alias map, so `chain(...)` and an aliased `c(...)` both count — and returns
    one ChainDecl { name, links } per chain: name is the assignment target, links are the
    positional-argument identifier names in source order. A file that declares no chain
    yields the empty list."""
    chains = []
    for right, name in _constructor_assignments(root, aliases, _CHAIN):
        chains.append({"name": name, "links": _positional_identifiers(right)})
    return chains


def extract_state_machines(root, source, aliases):
    """The state-machine recognizer of the §3.4 declaration graph, exposed for honest-test
    (§3.5). Finds every module-level assignment whose right side is a `state_machine(...)`
    call — recognized through the alias map, so a direct call and an aliased one both count —
    and returns one MachineDecl { name } per machine: name is the assignment target. A file
    that declares no state machine yields the empty list."""
    machines = []
    for _right, name in _constructor_assignments(root, aliases, _STATE_MACHINE):
        machines.append({"name": name})
    return machines


def _constructor_assignments(root, aliases, constructor):
    """(call_node, target_name) for each module-level `name = <constructor>(...)` assignment,
    in source order. The right side is a call whose function identifier resolves — through the
    alias map or as the literal constructor name — to constructor; the left side is a plain
    identifier target."""
    found = []
    for node in walk(root):
        if node.type != "assignment":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        if right.type != "call" or _canonical_name(right, aliases) != constructor:
            continue
        found.append((right, left.text.decode("utf-8")))
    return found


def _canonical_name(call_node, aliases):
    """The construction name a call resolves to, or None when the call is not a recognized
    construction. A direct constructor-name call counts, and an aliased one resolves through
    the alias map (§3.3)."""
    function = call_node.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    name = function.text.decode("utf-8")
    if name in aliases:
        return aliases[name]
    if name in _CONSTRUCTORS:
        return name
    return None


def _positional_identifiers(call_node):
    """The identifier names of a call's positional arguments, in source order. A keyword
    argument and a non-identifier positional carry no link name and are absent."""
    argument_list = call_node.child_by_field_name("arguments")
    return [
        child.text.decode("utf-8")
        for child in argument_list.named_children
        if child.type == "identifier"
    ]
