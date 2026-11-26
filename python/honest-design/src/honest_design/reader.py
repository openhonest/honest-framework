"""The .hd reader: source bytes -> IR, as a fold over the parse tree.

Pure over the tree. Parsing is delegated to honest-parse (the shared boundary); everything here is a
function of the tree and the source bytes. A malformed file yields a fault in the shared Result
shape, never a raised exception. Folding is dict-dispatch on node type — one handler per declaration
kind, so adding a primitive is adding a row, never branching control flow.
"""

import honest_parse

from honest_design import ir
from honest_design.result import err, fault, ok

# --- tree helpers --------------------------------------------------------------


def _field(node, name):
    return node.child_by_field_name(name)


def _text(node, source):
    return node.text.decode("utf-8", "replace")


def _field_text(node, name, source):
    return _text(_field(node, name), source)


def _children(node, type_name):
    return list(filter(lambda child: child.type == type_name, node.children))


def _unquote(s):
    """Strip a string token's surrounding quotes."""
    return s[1:-1]


# key text of a raises entry: an identifier is itself; a quoted code is unquoted.
_RAISES_TEXT = {"identifier": lambda t: t, "string": lambda t: t[1:-1]}


# --- types ---------------------------------------------------------------------


def _note(node, source):
    """The declaration's note, or "" when it has none: a key that is sometimes absent makes every
    consumer branch on its presence. A function may write its note in several clauses among the
    annotations; they read as one note, joined by a space."""
    return " ".join(_unquote(_field_text(n, "text", source)) for n in _children(node, "note"))


def _read_atom(node, source) -> ir.Atom:
    args = [_read_type(t, source) for g in _children(node, "generic_args") for t in _children(g, "type")]
    return {"name": _field_text(node, "name", source), "args": args}


def _read_type(node, source):
    """A type is a union of one or more atoms."""
    return [_read_atom(a, source) for a in _children(node, "type_atom")]


def _read_name_and_type(node, source):
    """The {name, type} record a field node and a param node both carry — ir.Field and ir.Param
    are the same shape, so one reader builds both rather than two copies of one body."""
    return {"name": _field_text(node, "name", source), "type": _read_type(_field(node, "type"), source)}


# a type declaration's value is a record (fields), an alias (a type), or foreign (a source it names
# and no fields, because describing someone else's object is a copy that drifts).
_TYPE_VALUE = {
    "record_type": lambda n, s: ([_read_name_and_type(f, s) for f in _children(n, "field")], [], ""),
    "type": lambda n, s: ([], _read_type(n, s), ""),
    "foreign_type": lambda n, s: ([], [], _unquote(_field_text(n, "source", s))),
}


def _read_type_decl(node, source) -> ir.TypeDecl:
    value = _field(node, "value")
    record, alias, foreign = _TYPE_VALUE[value.type](value, source)
    return {"name": _field_text(node, "name", source), "record": record, "alias": alias, "foreign": foreign, "note": _note(node, source)}


# --- sets, vocabularies, dispatch ---------------------------------------------


def _read_member(node, source) -> ir.SetMember:
    match _field(node, "description"):
        case None:
            description = ""
        case desc:
            description = _unquote(_text(desc, source))
    return {"value": _unquote(_field_text(node, "value", source)), "description": description}


def _read_set(node, source) -> ir.SetDecl:
    return {"name": _field_text(node, "name", source), "members": [_read_member(m, source) for m in _children(node, "set_member")], "note": _note(node, source)}


def _read_vocab(node, source) -> ir.Vocabulary:
    idents = _children(node, "identifier")
    return {"name": _text(idents[0], source), "sets": [_text(i, source) for i in idents[1:]], "note": _note(node, source)}


def _read_dispatch_entry(node, source) -> ir.DispatchEntry:
    """An entry, and the slice of the input its handler is fed when one is declared.

    `projection` is "" rather than absent when the entry does not declare one: a reader that
    sometimes omits a key makes every consumer branch on its presence, and the two cases mean
    different things only to whoever remembers which.
    """
    match _field(node, "projection"):
        case None:
            projection = ""
        case field:
            projection = _text(field, source)
    return {"key": _unquote(_field_text(node, "key", source)),
            "handler": _field_text(node, "handler", source),
            "projection": projection}


def _read_dispatch(node, source) -> ir.Dispatch:
    return {"name": _field_text(node, "name", source), "entries": [_read_dispatch_entry(e, source) for e in _children(node, "dispatch_entry")], "note": _note(node, source)}


def _read_example(node, source) -> ir.Example:
    return {
        "name": _field_text(node, "name", source),
        "chain": _field_text(node, "chain", source),
        "text": _unquote(_field_text(node, "text", source)),
    }


# --- functions -----------------------------------------------------------------

# edge stands on the input side (column 1) with the doors and readers: it is a way into the
# module, a pure function the world reaches by import. It differs from a door in that no I/O
# happens at it, and build-map sections it under its own "imported (pure)" heading.
_ROLE_COLUMN = {"boundary_in": 1, "reader": 1, "orchestrator": 2, "fn": 3, "boundary_out": 4, "edge": 1}


def _read_side_effect(node, source) -> ir.SideEffect:
    """One side of the world, with a dotted seam target split into the module and the door it enters.

    The colon decides first. A target that carries a colon is a kind and a free name,
    `HTTP:studio.local` or `file:design/data`, and the whole name after the first colon is free
    text, so no dot or slash in it splits and both halves stay "". A target with no colon is a
    seam when it carries exactly one dot, `honest-parse.parse_source`, which splits into the module
    and the door; no dot, or more than one, leaves both halves "". The number of dots in a host
    name or a file name is not a fact about the format, so the colon, not the dot count, tells a
    named side from a seam.
    """
    target = _unquote(_field_text(node, "target", source))
    module, dot, door = target.partition(".")
    is_seam = bool(dot) and ":" not in target and "." not in door
    module, door = (("", ""), (module, door))[is_seam]
    return {
        "direction": _field_text(node, "direction", source),
        "target": target,
        "module": module,
        "door": door,
    }


# inherits: hd=python/honest-design/honest-design.hd::_read_pure_call -> feature=python/honest-design/features/honest-design.feature::_read_pure_call returns the target without enclosing quotes -> test=python/honest-design/conformance/probe_read_pure_call_target.py::probe_read_pure_call_target
# hd: _read_pure_call
def _read_pure_call(node, source) -> str:
    return _unquote(_field_text(node, "target", source))


# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function preserves the legacy edge role in column 1 -> test=python/honest-design/conformance/probe_read_function_legacy_edge.py::probe_read_function_legacy_edge
# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function preserves repeated pure calls in source order -> test=python/honest-design/conformance/probe_read_function_repeated_pure_calls.py::probe_read_function_repeated_pure_calls
# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function omits pure_calls when no annotation is present -> test=python/honest-design/conformance/probe_read_function_absent_pure_calls.py::probe_read_function_absent_pure_calls
# hd: _read_function
def _read_function(node, source) -> ir.Function:
    match _field(node, "role"):
        case None:
            role = "fn"
        case role_node:
            role = _text(role_node, source)
    column = _ROLE_COLUMN.get(role)
    assert column is not None, f"Unexpected function role from the .hd grammar: {role!r}"
    signature = _children(node, "signature")[0]
    params_node = _children(signature, "params")[0]
    invokes = [_text(i, source) for inv in _children(node, "invokes") for i in _children(inv, "identifier")]
    raise_entries = (
        entry
        for clause in _children(node, "raises")
        for entry in filter(lambda child: child.type in _RAISES_TEXT, clause.children)
    )
    raises = [_RAISES_TEXT[entry.type](_text(entry, source)) for entry in raise_entries]
    pure_calls = [_read_pure_call(call, source) for call in _children(node, "pure_call")]
    pure_call_fields = ({}, {"pure_calls": pure_calls})[bool(pure_calls)]
    return {
        "name": _field_text(node, "name", source),
        "role": role,
        "column": column,
        "params": [_read_name_and_type(p, source) for p in _children(params_node, "param")],
        "ret": _read_type(_field(signature, "ret"), source),
        "side_effects": [_read_side_effect(se, source) for se in _children(node, "side_effect")],
        "invokes": invokes,
        "raises": raises,
        "note": _note(node, source),
        "awaited": bool(_children(node, "awaited")),
        **pure_call_fields,
    }


# --- chains, routes, entries, attributes --------------------------------------


def _read_chain(node, source) -> ir.Chain:
    body = _children(node, "chain_body")[0]
    return {"name": _field_text(node, "name", source), "links": [_text(i, source) for i in _children(body, "identifier")], "note": _note(node, source)}


def _read_expose(node, source) -> ir.Exposed:
    """A value the module presents to the honest-test runner: its kind (one of machine, schema,
    component, provider, gate) and the name it is exposed under, with the declaration's note."""
    return {"kind": _field_text(node, "kind", source), "name": _field_text(node, "name", source), "note": _note(node, source)}


def _read_route(node, source) -> ir.Route:
    method, _, path = _unquote(_field_text(node, "path", source)).partition(" ")
    match node.child_by_field_name("label"):
        case None:
            label = ""
        case label_node:
            label = _unquote(label_node.text.decode())
    return {"method": method, "path": path, "target": _field_text(node, "target", source), "label": label}


def _read_entry(node, source) -> ir.Entry:
    return {"callsite": _unquote(_field_text(node, "callsite", source)), "target": _field_text(node, "target", source)}


def _read_html_attr(node, source) -> ir.HtmlAttr:
    return {"attr": _unquote(_field_text(node, "attr", source)), "description": _unquote(_field_text(node, "description", source))}


def _read_layer(node, source):
    return _field_text(node, "name", source)


def _read_version(node, source):
    """The version the architect gives this declaration, as written. The reader keeps the string
    and never parses it: the format does not say what a version means, so comparing two of them
    is the reader's own business and nothing here orders them."""
    return _unquote(_field_text(node, "value", source))


def _read_store(node, source) -> ir.Store:
    """State held between calls: one pure function's answers by its arguments, and why."""
    return {"name": _field_text(node, "name", source), "fn": _field_text(node, "fn", source),
            "why": _unquote(_field_text(node, "why", source))}


def _read_surface(node, source):
    """One side list, inputs or outputs: set members, each a side of the world with an optional
    description. Several blocks read as one list."""
    return [_read_member(m, source) for m in _children(node, "set_member")]


def _read_env(node, source) -> ir.Env:
    """An environment variable the module reads: the name the deployment must supply, and its type."""
    return {"name": _field_text(node, "name", source), "type": _read_type(_field(node, "type"), source), "note": _note(node, source)}


def _read_surface_member(node, source) -> ir.SurfaceMember:
    """One surface: the id a rendered element must carry, and the element it lives in."""
    return {"id": _unquote(_field_text(node, "id", source)),
            "element": _field_text(node, "element", source)}


def _read_surfaces(node, source) -> ir.Surfaces:
    """A surfaces block. The members keep their declared order because that order is the
    contract: the page must render them in the sequence written here."""
    return {"name": _field_text(node, "name", source),
            "members": [_read_surface_member(c, source)
                        for c in filter(lambda c: c.type == "surface_member", node.named_children)]}


# body declaration -> (Module field, handler). Each handler is a function of (node, source).
_BODY = {
    "layer_decl": ("layer", _read_layer),
    "version_decl": ("version", _read_version),
    "env_decl": ("envs", _read_env),
    "store_decl": ("stores", _read_store),
    "inputs_decl": ("inputs", _read_surface),
    "outputs_decl": ("outputs", _read_surface),
    "type_decl": ("types", _read_type_decl),
    "set_decl": ("sets", _read_set),
    "vocabulary_decl": ("vocabularies", _read_vocab),
    "dispatch_decl": ("dispatches", _read_dispatch),
    "surfaces_decl": ("surfaces", _read_surfaces),
    "example_decl": ("examples", _read_example),
    "function_decl": ("functions", _read_function),
    "chain_decl": ("chains", _read_chain),
    "expose_decl": ("exposes", _read_expose),
    "route_decl": ("routes", _read_route),
    "entry_decl": ("entries", _read_entry),
    "html_attr_decl": ("html_attrs", _read_html_attr),
}


def _read_module(node, source) -> ir.Module:
    groups = {kind: [] for kind, _ in _BODY.values()}
    for child in filter(lambda child: child.type in _BODY, node.children):
        kind, read_child = _BODY[child.type]
        groups[kind].append(read_child(child, source))
    return {
        "name": _field_text(node, "name", source),
        "layer": (groups["layer"] or [""])[0],
        "version": (groups["version"] or [""])[0],
        "note": _note(node, source),
        "envs": groups["envs"],
        "stores": groups["stores"],
        "inputs": [m for block in groups["inputs"] for m in block],
        "outputs": [m for block in groups["outputs"] for m in block],
        "surface_declared": bool(groups["inputs"] or groups["outputs"]),
        "types": groups["types"],
        "sets": groups["sets"],
        "vocabularies": groups["vocabularies"],
        "dispatches": groups["dispatches"],
        "surfaces": groups["surfaces"],
        "examples": groups["examples"],
        "functions": groups["functions"],
        "chains": groups["chains"],
        "exposes": groups["exposes"],
        "routes": groups["routes"],
        "entries": groups["entries"],
        "html_attrs": groups["html_attrs"],
    }


# --- workspace declarations ----------------------------------------------------


def _read_rule(node, source) -> ir.Rule:
    match _field(node, "module"):
        case None:
            module = ""
        case module_node:
            module = _text(module_node, source)
    return {"id": _field_text(node, "id", source), "module": module, "statement": _unquote(_field_text(node, "statement", source))}


def _read_actor(node, source) -> ir.Actor:
    return {"name": _field_text(node, "name", source)}


def _read_flow(node, source) -> ir.Flow:
    body = _children(node, "flow_body")[0]
    return {
        "name": _field_text(node, "name", source),
        "group": _field_text(node, "group", source),
        "steps": [_text(i, source) for i in _children(body, "identifier")],
    }


# top-level declaration -> (Document field, handler).
_TOP = {
    "module_decl": ("modules", _read_module),
    "rule_decl": ("rules", _read_rule),
    "actor_decl": ("actors", _read_actor),
    "flow_decl": ("flows", _read_flow),
}


def _document(groups) -> ir.Document:
    return {
        "modules": groups["modules"],
        "rules": groups["rules"],
        "actors": groups["actors"],
        "flows": groups["flows"],
    }


def read_hd(source):
    """Read `.hd` source text into a Document IR, or a fault if the source is malformed.

    This is a boundary: the source arrives from outside and its type is not something the
    module can assume. A non-text source is refused by name here rather than allowed to fail
    as an AttributeError from inside the parse, which is what the promise above means."""
    match isinstance(source, str):
        case False:
            return err(fault("hd_source_not_text", f"read_hd takes .hd source as text, not {type(source).__name__}", "client", {}))
    source = source.encode("utf-8")
    root = honest_parse.parse(source, "hd").root_node
    match honest_parse.first_error_node(root):
        case None:
            pass
        case error:
            line, col = honest_parse.line_col(error)
            return err(fault("hd_syntax_error", f"Malformed .hd at line {line}, column {col}", "client", {"line": line, "col": col}))
    groups = {kind: [] for kind, _ in _TOP.values()}
    for child in filter(lambda child: child.type in _TOP, root.children):
        kind, read_child = _TOP[child.type]
        groups[kind].append(read_child(child, source))
    return ok(_document(groups))
