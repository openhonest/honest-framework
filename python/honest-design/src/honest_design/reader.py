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
    return honest_parse.node_text(node, source)


def _field_text(node, name, source):
    return _text(_field(node, name), source)


def _children(node, type_name):
    return [c for c in node.children if c.type == type_name]


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


def _read_field(node, source) -> ir.Field:
    return {"name": _field_text(node, "name", source), "type": _read_type(_field(node, "type"), source)}


# a type declaration's value is either a record (fields) or an alias (a type).
_TYPE_VALUE = {
    "record_type": lambda n, s: ([_read_field(f, s) for f in _children(n, "field")], []),
    "type": lambda n, s: ([], _read_type(n, s)),
}


def _read_type_decl(node, source) -> ir.TypeDecl:
    value = _field(node, "value")
    record, alias = _TYPE_VALUE[value.type](value, source)
    return {"name": _field_text(node, "name", source), "record": record, "alias": alias, "note": _note(node, source)}


# --- sets, vocabularies, dispatch ---------------------------------------------


def _read_member(node, source) -> ir.SetMember:
    desc = _field(node, "description")
    description = _unquote(_text(desc, source)) if desc is not None else ""
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
    projection = _field(node, "projection")
    return {"key": _unquote(_field_text(node, "key", source)),
            "handler": _field_text(node, "handler", source),
            "projection": _text(projection, source) if projection is not None else ""}


def _read_dispatch(node, source) -> ir.Dispatch:
    return {"name": _field_text(node, "name", source), "entries": [_read_dispatch_entry(e, source) for e in _children(node, "dispatch_entry")], "note": _note(node, source)}


def _read_example(node, source) -> ir.Example:
    return {
        "name": _field_text(node, "name", source),
        "chain": _field_text(node, "chain", source),
        "text": _unquote(_field_text(node, "text", source)),
    }


# --- functions -----------------------------------------------------------------

_ROLE_COLUMN = {"boundary_in": 1, "reader": 1, "orchestrator": 2, "boundary_out": 4}


def _read_param(node, source) -> ir.Param:
    return {"name": _field_text(node, "name", source), "type": _read_type(_field(node, "type"), source)}


def _read_side_effect(node, source) -> ir.SideEffect:
    return {"direction": _field_text(node, "direction", source), "target": _unquote(_field_text(node, "target", source))}


def _read_function(node, source) -> ir.Function:
    role_node = _field(node, "role")
    role = _text(role_node, source) if role_node is not None else "fn"
    signature = _children(node, "signature")[0]
    params_node = _children(signature, "params")[0]
    invokes = [_text(i, source) for inv in _children(node, "invokes") for i in _children(inv, "identifier")]
    raises = [_RAISES_TEXT[r.type](_text(r, source)) for rz in _children(node, "raises") for r in rz.children if r.type in _RAISES_TEXT]
    return {
        "name": _field_text(node, "name", source),
        "role": role,
        "column": _ROLE_COLUMN.get(role, 3),
        "params": [_read_param(p, source) for p in _children(params_node, "param")],
        "ret": _read_type(_field(signature, "ret"), source),
        "side_effects": [_read_side_effect(se, source) for se in _children(node, "side_effect")],
        "invokes": invokes,
        "raises": raises,
        "note": _note(node, source),
        "awaited": bool(_children(node, "awaited")),
    }


# --- chains, routes, entries, attributes --------------------------------------


def _read_chain(node, source) -> ir.Chain:
    body = _children(node, "chain_body")[0]
    return {"name": _field_text(node, "name", source), "links": [_text(i, source) for i in _children(body, "identifier")], "note": _note(node, source)}


def _read_route(node, source) -> ir.Route:
    parts = _unquote(_field_text(node, "path", source)).split(" ", 1)
    path = parts[1] if len(parts) > 1 else ""
    return {"method": parts[0], "path": path, "target": _field_text(node, "target", source)}


def _read_entry(node, source) -> ir.Entry:
    return {"callsite": _unquote(_field_text(node, "callsite", source)), "target": _field_text(node, "target", source)}


def _read_html_attr(node, source) -> ir.HtmlAttr:
    return {"attr": _unquote(_field_text(node, "attr", source)), "description": _unquote(_field_text(node, "description", source))}


def _read_layer(node, source):
    return _field_text(node, "name", source)


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
                        for c in node.named_children if c.type == "surface_member"]}


# body declaration -> (Module field, handler). Each handler is a function of (node, source).
_BODY = {
    "layer_decl": ("layer", _read_layer),
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
    "route_decl": ("routes", _read_route),
    "entry_decl": ("entries", _read_entry),
    "html_attr_decl": ("html_attrs", _read_html_attr),
}


def _read_module(node, source) -> ir.Module:
    pairs = [(_BODY[c.type][0], _BODY[c.type][1](c, source)) for c in node.children if c.type in _BODY]
    groups = {}
    for kind, value in pairs:
        groups.setdefault(kind, []).append(value)
    return {
        "name": _field_text(node, "name", source),
        "layer": (groups.get("layer") or [""])[0],
        "envs": groups.get("envs", []),
        "stores": groups.get("stores", []),
        "inputs": [m for block in groups.get("inputs", []) for m in block],
        "outputs": [m for block in groups.get("outputs", []) for m in block],
        "surface_declared": "inputs" in groups or "outputs" in groups,
        "types": groups.get("types", []),
        "sets": groups.get("sets", []),
        "vocabularies": groups.get("vocabularies", []),
        "dispatches": groups.get("dispatches", []),
        "surfaces": groups.get("surfaces", []),
        "examples": groups.get("examples", []),
        "functions": groups.get("functions", []),
        "chains": groups.get("chains", []),
        "routes": groups.get("routes", []),
        "entries": groups.get("entries", []),
        "html_attrs": groups.get("html_attrs", []),
    }


# --- workspace declarations ----------------------------------------------------


def _read_rule(node, source) -> ir.Rule:
    module_node = _field(node, "module")
    module = _text(module_node, source) if module_node is not None else ""
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
        "modules": groups.get("modules", []),
        "rules": groups.get("rules", []),
        "actors": groups.get("actors", []),
        "flows": groups.get("flows", []),
    }


def read_hd(source):
    """Read `.hd` source text into a Document IR, or a fault if the source is malformed.

    This is a boundary: the source arrives from outside and its type is not something the
    module can assume. A non-text source is refused by name here rather than allowed to fail
    as an AttributeError from inside the parse, which is what the promise above means."""
    if not isinstance(source, str):  # honest: ignore HC-P005: this line is the boundary the docstring describes
        return err(fault("hd_source_not_text", f"read_hd takes .hd source as text, not {type(source).__name__}", "client", {}))  # honest: ignore HC-P005: the fault names the type it refused (honest-type 9.5)
    source = source.encode("utf-8")
    root = honest_parse.parse(source, "hd").root_node
    error = honest_parse.first_error_node(root)
    if error is not None:
        line, col = honest_parse.line_col(error)
        return err(fault("hd_syntax_error", f"Malformed .hd at line {line}, column {col}", "client", {"line": line, "col": col}))
    pairs = [(_TOP[c.type][0], _TOP[c.type][1](c, source)) for c in root.children if c.type in _TOP]
    groups = {}
    for kind, value in pairs:
        groups.setdefault(kind, []).append(value)
    return ok(_document(groups))
