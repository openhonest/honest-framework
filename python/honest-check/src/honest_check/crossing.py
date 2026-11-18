"""The whole-package cores: the declaration-crossing rules (§2.1), the cross-file
reference rules (§HC-REF002/§HC-REF003), the orphan-function rule (§HC-R001) and
the identity rules (§HC-A001/§HC-A002). Each takes the whole package at once,
because its reference resolves across files; each returns Diagnostics as data."""

import re
from pathlib import Path

from honest_parse import walk

from ._util import choose, pick, read_or
from .context import build_context
from .decorators import decorator_target, decorators_of
from .diagnostics import diagnostic
from .nodes import _field, _text, called_name

_CROSSING_RULES = {"HC-R002", "HC-R003", "HC-R004", "HC-R005", "HC-REF005"}
_ROLE_DECORATORS = {"link", "recognizer", "boundary", "helper", "orchestrator"}
_CALL_TYPES = {"call", "call_expression"}
_CODE_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".rb", ".go")

# The three-valued reading of a function's absence behaviour (§HC-R004).
_RETURNS_NOTHING = "RETURNS_NOTHING"
_RETURNS_VALUE = "RETURNS_VALUE"
_INDETERMINATE = "INDETERMINATE"
# Return-value node types the source shows cannot be None: literals and constructors.
_VALUE_TYPES = {
    "integer", "float", "string", "concatenated_string", "true", "false",
    "list", "dictionary", "set", "tuple", "list_comprehension",
    "dictionary_comprehension", "set_comprehension", "lambda",
}


def _top_level_function_defs(ctx):
    top = ctx["root"].named_children
    direct = list(filter(lambda n: n.type == "function_definition", top))
    decorated = filter(lambda n: n.type == "decorated_definition", top)
    inner = map(
        lambda d: next(filter(lambda c: c.type == "function_definition", d.named_children), None),
        decorated,
    )
    return direct + list(filter(lambda f: f is not None, inner))


def _function_name(fdef):
    return _field(fdef, "name").text.decode("utf-8")


def _own_body_nodes(node):
    # A node's descendants within its own body, not crossing into a nested
    # function: a return/yield inside a function defined within the declared one
    # belongs to that inner function (§HC-R004, §HC-R005), so the walk stops at a
    # function_definition the same way both rules draw the bound.
    kids = list(filter(lambda c: c.type != "function_definition", node.children))
    return kids + [deep for kid in kids for deep in _own_body_nodes(kid)]


# ---- the declaration-crossing core (§2.1) -----------------------------------


def _code_functions(sources):
    out = {}
    for source in sources:
        ctx = build_context(source["text"], source["path"], {})
        for fdef in filter(lambda n: n.type == "function_definition", ctx["nodes"]):
            out[_function_name(fdef)] = {"fdef": fdef, "ctx": ctx}
    return out


def _is_async_def(fdef):
    return any(c.type == "async" for c in fdef.children)


def _declares_absence(function):
    absence = {"NOTHING", "Absent", "None"}
    return any(part["name"] in absence for part in read_or(function, "ret", []))


def _return_value_node(return_node):
    return next(filter(lambda c: c.type != "return", return_node.children), None)


def _return_is_none(return_node):
    value = _return_value_node(return_node)
    return bool(value is None or value.type == "none")


def _all_returns_value(returns):
    return all(_return_value_node(r).type in _VALUE_TYPES for r in returns)


def code_absence(fdef):
    # Three-valued reading of whether the function can answer the host nothing
    # (§HC-R004). A none/bare return or an end-fallthrough (zero returns) is
    # RETURNS_NOTHING; returns that are all source-provable values are
    # RETURNS_VALUE; a return whose value the checker cannot resolve (subscript,
    # .get, call, ...) leaves the function INDETERMINATE and the rule skips it.
    returns = list(filter(lambda n: n.type == "return_statement", _own_body_nodes(fdef)))
    nothing = len(returns) == 0 or any(_return_is_none(r) for r in returns)
    return pick(
        nothing,
        lambda: _RETURNS_NOTHING,
        lambda: choose(_all_returns_value(returns), _RETURNS_VALUE, _INDETERMINATE),
    )


def _body_yields(fdef):
    return any(n.type in {"yield", "yield_expression"} for n in _own_body_nodes(fdef))


def _r003_one(function, entry):
    disagree = _is_async_def(entry["fdef"]) != function["awaited"]
    return pick(
        disagree,
        lambda: [diagnostic(entry["ctx"], "HC-R003", "error", "declaration and code disagree about awaiting", entry["fdef"])],
        lambda: [],
    )


def _r004_one(function, entry):
    absence = code_absence(entry["fdef"])
    disagree = (absence == _RETURNS_NOTHING) != _declares_absence(function)
    fire = absence != _INDETERMINATE and disagree
    return pick(
        fire,
        lambda: [diagnostic(entry["ctx"], "HC-R004", "error", "declaration and code disagree about absence", entry["fdef"])],
        lambda: [],
    )


def _r005_one(function, entry):
    fire = _body_yields(entry["fdef"]) and not _declares_absence(function)
    return pick(
        fire,
        lambda: [diagnostic(entry["ctx"], "HC-R005", "error", "a declared function yields while its declaration returns a value", entry["fdef"])],
        lambda: [],
    )


def _per_function_rule(rule_one, declaration, code_functions):
    out = []
    for function in declaration["functions"]:
        entry = read_or(code_functions, function["name"], None)
        out.extend(pick(entry is None, lambda: [], lambda: rule_one(function, entry)))
    return out


def _called_names_in(ctx, fdef):
    calls = filter(lambda n: n.type in _CALL_TYPES, walk(fdef))
    names = map(lambda c: called_name(ctx, c), calls)
    return set(filter(lambda n: n is not None, names))


def _r002(declaration, code_functions):
    inward = set(
        map(
            lambda f: f["name"],
            filter(lambda f: f["role"] in {"orchestrator", "boundary_in"}, declaration["functions"]),
        )
    )
    outputs = filter(lambda f: f["role"] == "boundary_out", declaration["functions"])
    out = []
    for function in outputs:
        entry = read_or(code_functions, function["name"], None)
        out.extend(pick(entry is None, lambda: [], lambda: _r002_one(entry, inward)))
    return out


def _r002_one(entry, inward):
    hits = _called_names_in(entry["ctx"], entry["fdef"]) & inward
    return pick(
        len(hits) > 0,
        lambda: [diagnostic(entry["ctx"], "HC-R002", "error", "output boundary invokes an orchestrator or input boundary", entry["fdef"])],
        lambda: [],
    )


def _exported_names(export_source):
    empty = bool(export_source is None or export_source == b"")
    return pick(empty, lambda: set(), lambda: _read_all(export_source))


def _read_all(export_source):
    ctx = build_context(export_source, "exports.py", {})
    assignments = filter(lambda n: n.type == "assignment", ctx["nodes"])
    all_assigns = filter(lambda a: _text(_field(a, "left")) == "__all__", assignments)
    names = set()
    for assignment in all_assigns:
        right = _field(assignment, "right")
        strings = pick(
            right is not None and right.type == "list",
            lambda: filter(lambda c: c.type == "string", right.named_children),
            lambda: [],
        )
        names.update(s.text.decode("utf-8")[1:-1] for s in strings)
    return names


def _undeclared_diag(code_functions, anchor, name):
    entry = read_or(code_functions, name, None)
    return pick(
        entry is not None,
        lambda: diagnostic(entry["ctx"], "HC-REF005", "error", f"{name} is exported by the module and declared in no .hd", entry["fdef"]),
        lambda: _ref005_diag(anchor, name),
    )


def _ref005(declaration, code_functions, export_source, sources):
    # HC-REF005 holds the surface to the declaration, not the declaration to the
    # surface (spec §HC-REF005). `declared - defined` is the allowed lag — the .hd
    # legitimately running ahead of the code it will get — and emits nothing. The
    # only finding is the reverse: a function the code exports in __all__ that no
    # .hd declares, code that ran ahead of the record.
    declared = set(f["name"] for f in declaration["functions"])
    undeclared = _exported_names(export_source) - declared
    anchor = _first_ctx(sources)
    return pick(
        anchor is not None,
        lambda: [_undeclared_diag(code_functions, anchor, name) for name in undeclared],
        lambda: [],
    )


def _first_ctx(sources):
    return pick(
        len(sources) == 0,
        lambda: None,
        lambda: build_context(sources[0]["text"], sources[0]["path"], {}),
    )


def _ref005_diag(ctx, name):
    return {
        "rule_id": "HC-REF005",
        "severity": "error",
        "message": f"the declaration names {name}, which the code defines nowhere",
        "source_location": ctx["path"],
        "context": "",
        "fixable": False,
    }


def cross_declaration(sources, declaration, export_source, rule_ids):
    """Cross one module's .hd against the whole package, running only the crossing
    rules named in rule_ids (all five when empty) (§2.1)."""
    active = choose(len(rule_ids) == 0, _CROSSING_RULES, set(rule_ids))
    code_functions = _code_functions(sources)
    return (
        pick("HC-R003" in active, lambda: _per_function_rule(_r003_one, declaration, code_functions), lambda: [])
        + pick("HC-R004" in active, lambda: _per_function_rule(_r004_one, declaration, code_functions), lambda: [])
        + pick("HC-R005" in active, lambda: _per_function_rule(_r005_one, declaration, code_functions), lambda: [])
        + pick("HC-R002" in active, lambda: _r002(declaration, code_functions), lambda: [])
        + pick("HC-REF005" in active, lambda: _ref005(declaration, code_functions, export_source, sources), lambda: [])
    )


# ---- the cross-file reference core (§HC-REF002, §HC-REF003) ------------------

_INCLUDE_RE = re.compile(r"{%\s*(?:extends|include)\s+[\"']([^\"']+)[\"']")
_CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"')
_CSS_CLASS_RE = re.compile(r"\.([A-Za-z_][\w-]*)")
_HX_ACTION_RE = re.compile(r'hx-(get|post|put|patch|delete)\s*=\s*"([^"]*)"')
_HF_ATTR_RE = re.compile(r'(hf-[a-z-]+)\s*=\s*"([^"]*)"')
_ROUTE_METHOD_RE = re.compile(r'"method"\s*:\s*"([^"]*)"')
_ROUTE_PATH_RE = re.compile(r'"path"\s*:\s*"([^"]*)"')
_INTERPOLATION_RE = re.compile(r"\{\{[^}]*\}\}|\{[^}]*\}")


def _reference_diagnostic(rule_id, source, message):
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": message,
        "source_location": source["path"],
        "context": "",
        "fixable": False,
    }


def _classes_in(text):
    out = set()
    for attribute in _CLASS_ATTR_RE.findall(text):
        out.update(attribute.split())
    return out


def _ref002(template, text, template_names):
    targets = _INCLUDE_RE.findall(text)
    dead = filter(
        lambda target: Path(target).name not in template_names and target not in template_names,
        targets,
    )
    return [
        _reference_diagnostic("HC-REF002", template, f"include/extends target {d!r} resolves to no template")
        for d in dead
    ]


def _ref003(template, text, defined_classes):
    dead = filter(lambda c: c not in defined_classes, _classes_in(text))
    return [
        _reference_diagnostic("HC-REF003", template, f"class {c!r} resolves to no defined rule")
        for c in dead
    ]


def _normalize_path(path):
    return pick(path is None, lambda: None, lambda: _INTERPOLATION_RE.sub("{}", path))


def _dict_string(dict_node, key):
    pairs = filter(lambda c: c.type == "pair", dict_node.named_children)
    match = next(
        filter(lambda p: _field(p, "key").type == "string" and _field(p, "key").text.decode("utf-8")[1:-1] == key, pairs),
        None,
    )
    value = _field(match, "value")
    return pick(value is not None and value.type == "string", lambda: value.text.decode("utf-8")[1:-1], lambda: None)


def _route_map(code_sources):
    armed = False
    patterns = set()
    for source in code_sources:
        ctx = build_context(source["text"], source["path"], {})
        route_fns = list(filter(
            lambda n: n.type == "function_definition" and _text(_field(n, "name")) == "route_table",
            ctx["nodes"],
        ))
        armed = armed or len(route_fns) > 0
        for fn in route_fns:
            for route in filter(lambda n: n.type == "dictionary", walk(fn)):
                patterns.add((_dict_string(route, "method"), _normalize_path(_dict_string(route, "path"))))
    return {"armed": armed, "patterns": patterns}


def _ref001(template, text, route_map):
    sites = _HX_ACTION_RE.findall(text)
    dead = filter(
        lambda site: (site[0].upper(), _normalize_path(site[1])) not in route_map["patterns"],
        sites,
    )
    return [
        _reference_diagnostic("HC-REF001", template, f"template action targets {s[0].upper()} {s[1]!r}, which no route mounts")
        for s in dead
    ]


def _ref004(template, text, format_vocabulary):
    refs = filter(lambda ref: "{" not in ref[1], _HF_ATTR_RE.findall(text))
    enumerated = filter(lambda ref: read_or(format_vocabulary, ref[0], None) is not None, refs)
    dead = filter(lambda ref: ref[1] not in read_or(format_vocabulary, ref[0], []), enumerated)
    return [
        _reference_diagnostic("HC-REF004", template, f"attribute {a}={v!r} names no member of the declared format vocabulary")
        for a, v in dead
    ]


def check_references(sources, format_vocabulary):
    """Resolve cross-file references over the whole discovered set: a template action
    against the route map the code's route_table() declares (§HC-REF001), an
    include/extends target against the template set (§HC-REF002), an emitted class
    against the union of stylesheet classes (§HC-REF003), and a behavioural hf-* value
    against the supplied format vocabulary (§HC-REF004). A missing route_table stands
    HC-REF001 down; a NOTHING format vocabulary stands HC-REF004 down."""
    templates = list(filter(lambda s: s["path"].endswith((".html", ".htm")), sources))
    stylesheets = filter(lambda s: s["path"].endswith(".css"), sources)
    code = filter(lambda s: s["path"].endswith(_CODE_SUFFIXES), sources)
    template_names = set(Path(s["path"]).name for s in templates)
    route_map = _route_map(list(code))
    defined_classes = set()
    for stylesheet in stylesheets:
        defined_classes.update(_CSS_CLASS_RE.findall(stylesheet["text"].decode("utf-8")))
    out = []
    for template in templates:
        text = template["text"].decode("utf-8")
        out.extend(pick(route_map["armed"], lambda: _ref001(template, text, route_map), lambda: []))
        out.extend(_ref002(template, text, template_names))
        out.extend(_ref003(template, text, defined_classes))
        out.extend(pick(format_vocabulary is None, lambda: [], lambda: _ref004(template, text, format_vocabulary)))
    return out


# ---- the whole-program role core (§HC-R001) ---------------------------------


def _has_role_decorator(ctx, fdef):
    return any(decorator_target(d) in _ROLE_DECORATORS for d in decorators_of(ctx, fdef))


def _role_entries(sources):
    entries = []
    for source in sources:
        ctx = build_context(source["text"], source["path"], {})
        for fdef in _top_level_function_defs(ctx):
            entries.append({"name": _function_name(fdef), "fdef": fdef, "ctx": ctx})
    return entries


def _roled_names(entries, declaration):
    declared = pick(
        declaration is None,
        lambda: set(),
        lambda: set(f["name"] for f in declaration["functions"]),
    )
    decorated = set(e["name"] for e in filter(lambda e: _has_role_decorator(e["ctx"], e["fdef"]), entries))
    return declared | decorated


def _call_graph(entries):
    names = set(e["name"] for e in entries)
    graph = {}
    for entry in entries:
        graph[entry["name"]] = _called_names_in(entry["ctx"], entry["fdef"]) & names
    return graph


def _reachable(roots, graph):
    seen = set(roots)
    frontier = list(roots)
    while frontier:
        node = frontier.pop()
        fresh = read_or(graph, node, set()) - seen
        seen |= fresh
        frontier.extend(fresh)
    return seen


def _emit_orphans(entries, roled):
    reachable = _reachable(roled, _call_graph(entries))
    orphans = filter(lambda e: e["name"] not in reachable, entries)
    return [
        diagnostic(e["ctx"], "HC-R001", "error", "orphan function: no role, not reachable", e["fdef"])
        for e in orphans
    ]


def check_roles(sources, declaration):
    """Run the whole-program orphan rule HC-R001: a top-level function neither roled
    nor reachable from the roled set is an orphan; with no roles adopted the rule
    stands down (§HC-R001)."""
    entries = _role_entries(sources)
    roled = _roled_names(entries, declaration)
    return pick(len(roled) == 0, lambda: [], lambda: _emit_orphans(entries, roled))


# ---- the whole-program auth core (§HC-A001, §HC-A002) -----------------------


def _has_provider(ctx):
    calls = filter(lambda n: n.type in _CALL_TYPES, ctx["nodes"])
    return any(called_name(ctx, c) == "register_auth_provider" for c in calls)


def _keyword_true(decorator, name):
    from .decorators import _keyword_value

    return _keyword_value(decorator, name) == "True"


def _is_authorizing_link(ctx, fdef):
    return any(
        decorator_target(d) == "link" and _keyword_true(d, "authorizes")
        for d in decorators_of(ctx, fdef)
    )


def _authorizing_links(ctx):
    links = filter(lambda f: _is_authorizing_link(ctx, f), _top_level_function_defs(ctx))
    return [{"name": _function_name(f), "fdef": f, "ctx": ctx} for f in links]


def _references_actor(entry):
    identifiers = filter(lambda n: n.type == "identifier", walk(entry["fdef"]))
    return any(n.text.decode("utf-8") == "actor" for n in identifiers)


def _auth_diagnostic(rule_id, severity, entry, message):
    return diagnostic(entry["ctx"], rule_id, severity, message, entry["fdef"])


def _a001(links):
    return pick(
        len(links) > 0,
        lambda: [_auth_diagnostic("HC-A001", "warning", links[0], "no AuthProvider registered; actor-using operations are unverifiable")],
        lambda: [],
    )


def _a002(links):
    firing = filter(lambda e: not _references_actor(e), links)
    return [
        _auth_diagnostic("HC-A002", "error", e, "actor trusted from request input instead of the boundary")
        for e in firing
    ]


def check_auth(sources):
    """Run the two identity rules over the project's code as one set: HC-A001 warns
    when no provider is registered yet an authorizing link exists; HC-A002 errors on
    an authorizing link that never names the boundary-resolved actor (§HC-A001,
    §HC-A002)."""
    links = []
    registered = False
    for source in filter(lambda s: s["path"].endswith(_CODE_SUFFIXES), sources):
        ctx = build_context(source["text"], source["path"], {})
        registered = registered or _has_provider(ctx)
        links.extend(_authorizing_links(ctx))
    return pick(registered, lambda: _a002(links), lambda: _a001(links))
