"""Construction-call reading: vocabularies, bindings, composed types, feature
flags, and the import-bound writer/collect names the state rules resolve (§4.1,
§HC004/§HC005, §7, §HC-ST001/§HC-ST002). Each reads data off a parsed call or
import and returns it; none runs the code."""

from honest_parse import walk

from ._util import choose, pick, read_or
from .nodes import (
    _field,
    _text,
    bare_or_final_name,
    call_arguments,
    called_name,
    canonical_name,
    literal_string,
    string_members,
)

_PERSIST_WRITERS = {"transaction", "apply"}


def _first(items):
    return pick(len(items) == 0, lambda: None, lambda: items[0])


def _pairs_of(node):
    return pick(
        node is None or node.type != "dictionary",
        lambda: [],
        lambda: list(filter(lambda c: c.type == "pair", node.named_children)),
    )


def _dict_string_keys(node):
    return set(literal_string(_field(p, "key")) for p in _pairs_of(node))


def base_types_of(ctx, dictionary_node):
    """The base-type map of a vocabulary's first-argument dict: each name to a
    BaseType record (§4.1). A 'set' type carries its members; a 'predicate' type
    carries its recognizer node."""
    out = {}
    for pair in _pairs_of(dictionary_node):
        name = literal_string(_field(pair, "key"))
        value = _field(pair, "value")
        out[name] = choose(
            value.type == "set",
            {"kind": "set", "members": set(string_members(ctx, value)), "recognizer": None},
            {"kind": "predicate", "members": None, "recognizer": value},
        )
    return out


# inherits: hd=python/honest-check/honest-check.hd::_value_names -> feature=specs/features/honest-check.feature::_value_names reads an optional capture base name -> test=python/honest-check/conformance/probe_value_names_optional_capture.py::probe_value_names_optional_capture
# hd: _value_names
def _value_names(ctx, node):
    """Read a literal capture name or the literal name inside an Honest Type maybe."""
    match node is not None and node.type:
        case "string":
            return {literal_string(node)}
        case "call":
            arguments = call_arguments(ctx, node)
            positionals = list(filter(lambda arg: arg.type != "comment", arguments["positionals"]))
            optional_literal = (
                canonical_name(ctx, node) == "maybe"
                and not arguments["keywords"]
                and len(positionals) == 1
                and positionals[0].type == "string"
            )
            return pick(optional_literal, lambda: {literal_string(positionals[0])}, set)
        case _:
            return set()


# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types preserves composed names from keyword declarations -> test=python/honest-check/conformance/probe_vocabulary_types_composed_keyword.py::probe_vocabulary_types_composed_keyword
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types returns empty composed fields when declarations are omitted -> test=python/honest-check/conformance/probe_vocabulary_types_composed_omitted.py::probe_vocabulary_types_composed_omitted
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types preserves composed names from positional declarations -> test=python/honest-check/conformance/probe_vocabulary_types_composed_positional.py::probe_vocabulary_types_composed_positional
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types preserves the base name inside an optional capture -> test=python/honest-check/conformance/probe_vocabulary_types_optional_capture.py::probe_vocabulary_types_optional_capture
# hd: vocabulary_types
def vocabulary_types(ctx, vocab_call):
    """Read base and composed names, the base map, and composed base references."""
    arguments = call_arguments(ctx, vocab_call)
    positionals = arguments["positionals"]
    first = _first(positionals)
    base = pick(first is None, lambda: {}, lambda: base_types_of(ctx, first))
    collection = read_or(arguments["keywords"], "composed_types", _first(positionals[1:]))
    elements = pick(collection is None, lambda: [], lambda: collection.named_children)
    composed_type_names = set()
    composed = []
    for call in filter(lambda element: element.type == "call", elements):
        declaration = call_arguments(ctx, call)
        positionals = declaration["positionals"]
        keywords = declaration["keywords"]
        name = _first(positionals)
        name_node = choose(name is not None and name.type == "string", name, None)
        composed_type_names.update(pick(name_node is not None, lambda: [literal_string(name_node)], list))
        requires = read_or(keywords, "requires", _first(positionals[1:]))
        captures = read_or(keywords, "captures", _first(positionals[2:]))
        composed.append({
            "name_node": name_node,
            "requires_bases": _dict_string_keys(requires),
            "captures_bases": _value_names(ctx, captures),
        })
    return {
        "base_names": set(base),
        "base_types": base,
        "composed_type_names": composed_type_names,
        "composed": composed,
    }


def binding_keys(ctx, binding_call):
    """The type names a binding(...) call binds — the keys of its first-argument
    table (§HC004, §HC005)."""
    arguments = call_arguments(ctx, binding_call)
    return _dict_string_keys(_first(arguments["positionals"]))


def binding_slots(ctx, binding_call):
    """The type-name → slot-name map a binding(...) call declares — each first-argument
    table entry's key string mapped to its value string (§HC-P013)."""
    arguments = call_arguments(ctx, binding_call)
    node = _first(arguments["positionals"])
    out = {}
    for pair in _pairs_of(node):
        out[literal_string(_field(pair, "key"))] = literal_string(_field(pair, "value"))
    return out


def _module_assignments(ctx):
    top = ctx["root"].named_children
    expressions = filter(lambda s: s.type == "expression_statement", top)
    inner = map(
        lambda e: pick(len(e.named_children) == 0, lambda: None, lambda: e.named_children[0]),
        expressions,
    )
    return filter(lambda a: a is not None and a.type == "assignment", inner)


def _assignment_name(assignment):
    left = _field(assignment, "left")
    return pick(
        left is not None and left.type == "identifier",
        lambda: left.text.decode("utf-8"),
        lambda: None,
    )


def construction_maps(ctx):
    """Each file-local variable bound to a vocabulary(...) or binding(...) call,
    mapped to that call node (§HC004, §HC005)."""
    out = {}
    for assignment in _module_assignments(ctx):
        name = _assignment_name(assignment)
        right = _field(assignment, "right")
        resolved = pick(
            right is not None and right.type == "call",
            lambda: canonical_name(ctx, right),
            lambda: None,
        )
        out.update(
            pick(
                name is not None and resolved in {"vocabulary", "binding"},
                lambda: {name: right},
                lambda: {},
            )
        )
    return out


def _resolve_construction(ctx, node, construction):
    name = pick(
        node is not None and node.type == "identifier",
        lambda: node.text.decode("utf-8"),
        lambda: None,
    )
    return read_or(construction, name, None)


def _classify_pair(ctx, call, construction):
    arguments = call_arguments(ctx, call)
    positionals = arguments["positionals"]
    vocab_node = pick(len(positionals) >= 2, lambda: positionals[1], lambda: None)
    bind_node = read_or(arguments["keywords"], "bind", None)
    vocab = _resolve_construction(ctx, vocab_node, construction)
    binding = _resolve_construction(ctx, bind_node, construction)
    return pick(
        vocab is not None and binding is not None,
        lambda: [([vocab], binding)],
        lambda: [],
    )


def _link_pair(ctx, call, construction):
    arguments = call_arguments(ctx, call)
    accepts = _resolve_construction(ctx, read_or(arguments["keywords"], "accepts", None), construction)
    emits = _resolve_construction(ctx, read_or(arguments["keywords"], "emits", None), construction)
    bind = _resolve_construction(ctx, read_or(arguments["keywords"], "bind", None), construction)
    vocabs = list(filter(lambda v: v is not None, [accepts, emits]))
    return pick(
        bind is not None and len(vocabs) > 0,
        lambda: [(vocabs, bind)],
        lambda: [],
    )


_PAIR_READERS = {"classify": _classify_pair, "link": _link_pair}


def vocabulary_binding_pairs(ctx):
    """Each (vocabulary calls, binding call) a classify or link pairs by name
    (§HC004, §HC005)."""
    construction = construction_maps(ctx)
    calls = filter(lambda n: n.type == "call", ctx["nodes"])
    out = []
    for call in calls:
        reader = read_or(_PAIR_READERS, called_name(ctx, call), None)
        out.extend(pick(reader is None, lambda: [], lambda: reader(ctx, call, construction)))
    return out


def _module_dict_named(ctx, name):
    assignments = _module_assignments(ctx)
    match = next(filter(lambda a: _assignment_name(a) == name, assignments), None)
    right = _field(match, "right")
    return choose(right is not None and right.type == "dictionary", right, None)


def _states_of(ctx, value):
    pairs = _pairs_of(value)
    states_pair = next(filter(lambda p: literal_string(_field(p, "key")) == "states", pairs), None)
    states_node = _field(states_pair, "value")
    return pick(states_node is None, lambda: set(), lambda: set(string_members(ctx, states_node)))


def features_vocabulary(ctx):
    """The feature-flag vocabulary a module-scope FEATURES dict declares — each flag
    mapped to its states set (§7, HC-HF001/HC-HF002)."""
    node = _module_dict_named(ctx, "FEATURES")
    return {
        literal_string(_field(p, "key")): _states_of(ctx, _field(p, "value"))
        for p in _pairs_of(node)
    }


# inherits: hd=python/honest-check/honest-check.hd::module_dict_literals -> feature=specs/features/honest-check.feature::module_dict_literals distinguishes an empty FEATURES literal from an unreadable binding -> test=python/honest-check/conformance/probe_module_dict_literals_empty_features.py::probe_module_dict_literals_empty_features
# hd: module_dict_literals
def module_dict_literals(ctx):
    """Each module-scope name bound to a dict literal, mapped to its string-key set
    (§7, HC-HF002)."""
    out = {}
    for assignment in _module_assignments(ctx):
        name = _assignment_name(assignment)
        right = _field(assignment, "right")
        keys = pick(
            right is not None and right.type == "dictionary",
            lambda: _dict_string_keys(right),
            lambda: None,
        )
        out.update(
            pick(name is not None and keys is not None, lambda: {name: keys}, lambda: {})
        )
    return out


def feature_state_flag(ctx, call_node):
    """The flag a feature_state(state, "flag") call names — its second positional
    string literal — or None (§7)."""
    name = called_name(ctx, call_node)
    positionals = call_arguments(ctx, call_node)["positionals"]
    second = pick(len(positionals) >= 2, lambda: positionals[1], lambda: None)
    return pick(
        name == "feature_state" and second is not None and second.type == "string",
        lambda: literal_string(second),
        lambda: None,
    )


def _framework_import_binds(ctx, module):
    """Each local name an `from <module> import ...` binds, mapped to the original
    imported name."""
    froms = filter(
        lambda n: n.type == "import_from_statement"
        and _text(_field(n, "module_name")) == module,
        ctx["nodes"],
    )
    binds = {}
    for statement in froms:
        module_node = _field(statement, "module_name")
        imports = filter(
            lambda c: c != module_node and c.type in {"aliased_import", "dotted_name"},
            statement.named_children,
        )
        for imported in imports:
            binds.update(_one_import_bind(imported))
    return binds


def _one_import_bind(node):
    return choose(
        node.type == "aliased_import",
        {
            _text(_field(node, "alias")): _text(_field(node, "name")),
        },
        {node.text.decode("utf-8"): node.text.decode("utf-8")},
    )


def persist_write_targets(ctx):
    """The local call targets bound through a honest_persist import to a declared
    writer (transaction, apply) (§HC-ST001)."""
    binds = _framework_import_binds(ctx, "honest_persist")
    writers = filter(lambda item: item[1] in _PERSIST_WRITERS, binds.items())
    return set(map(lambda item: item[0], writers))


def _import_source(import_node):
    return _text(_field(import_node, "source")).strip('"').strip("'")


def _specifier_local(specifier):
    idents = list(filter(lambda c: c.type == "identifier", specifier.named_children))
    return idents[-1].text.decode("utf-8")


def _collect_locals(import_node):
    specifiers = filter(lambda n: n.type == "import_specifier", walk(import_node))
    collects = filter(lambda s: _text(_field(s, "name")) == "collect", specifiers)
    return set(map(_specifier_local, collects))


def dom_collect_names(ctx):
    """The local names a JavaScript file binds to honest-dom's `collect` through its
    imports (§HC-ST002)."""
    imports = filter(lambda n: n.type == "import_statement", ctx["nodes"])
    dom_imports = filter(lambda i: _import_source(i) == "honest-dom", imports)
    names = set()
    for import_node in dom_imports:
        names.update(_collect_locals(import_node))
    return names


_JS_CALL_TYPES = {"call", "call_expression"}


def value_calls_collect(value_node, collect_names):
    """True when a bound value calls one of the resolved `collect` names anywhere
    inside it (§HC-ST002)."""
    calls = filter(lambda n: n.type in _JS_CALL_TYPES, walk(value_node))
    return any(bare_or_final_name(_field(c, "function")) in collect_names for c in calls)
