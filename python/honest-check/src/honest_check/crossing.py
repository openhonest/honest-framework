"""The whole-package cores: the declaration-crossing rules (§2.1), the cross-file
reference rules (§HC-REF002/§HC-REF003), the orphan-function rule (§HC-R001) and
the identity rules (§HC-A001/§HC-A002). Each takes the whole package at once,
because its reference resolves across files; each returns Diagnostics as data."""

import builtins
import codecs
import inspect
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


# inherits: hd=python/honest-check/honest-check.hd::_exported_names -> feature=specs/features/honest-check.feature::_exported_names returns an empty set when export source is omitted -> test=python/honest-check/conformance/probe__exported_names_omitted.py::probe__exported_names_omitted
# inherits: hd=python/honest-check/honest-check.hd::_exported_names -> feature=specs/features/honest-check.feature::_exported_names preserves the supplied initializer result -> test=python/honest-check/conformance/probe__exported_names_supplied.py::probe__exported_names_supplied
# hd: _exported_names
def _exported_names(export_source):
    return pick(export_source == b"", set, lambda: _read_all(export_source))


# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all reads literal export names including an empty list -> test=python/honest-check/conformance/probe__read_all_literal.py::probe__read_all_literal
# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all returns NOTHING when no unique literal export list is present -> test=python/honest-check/conformance/probe__read_all_invalid.py::probe__read_all_invalid
# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all distinguishes direct export list writes from ordinary reads -> test=python/honest-check/conformance/probe__read_all_direct_writes.py::probe__read_all_direct_writes
# hd: _read_all
def _read_all(export_source):
    """Read an unambiguous literal export list from an initializer's syntax."""
    # Python normalizes physical newlines before tokenizing, including inside strings.
    source = export_source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    root = build_context(source, "exports.py", {})["root"]
    assignments = [
        child
        for statement in filter(lambda node: node.type == "expression_statement", root.named_children)
        for child in filter(lambda node: node.type == "assignment", statement.named_children)
    ]
    all_assigns = list(filter(lambda node: _text(_field(node, "left")) == "__all__", assignments))
    assigned = pick(len(all_assigns) == 1, lambda: _field(all_assigns[0], "right"), lambda: None)
    binding_fields = {
        "assignment": "left", "augmented_assignment": "left", "for_statement": "left",
        "named_expression": "name", "as_pattern": "alias",
        "class_definition": "name", "function_definition": "name",
    }
    scope_kinds = {"class_definition", "function_definition", "lambda"}
    pattern_kinds = {"pattern_list", "list_pattern", "tuple_pattern", "list_splat_pattern", "expression_list"}
    mutations = {
        "__all__.append", "__all__.extend", "__all__.insert", "__all__.remove", "__all__.pop",
        "__all__.clear", "__all__.sort", "__all__.reverse", "__all__.__setitem__", "__all__.__delitem__",
    }
    pending = list(root.named_children)
    writes = 0
    while pending:
        node = pending.pop()
        scope_body = pick(node.type in scope_kinds, lambda: _field(node, "body"), lambda: None)
        pending.extend(filter(lambda child: child != scope_body, node.named_children))
        field = read_or(binding_fields, node.type, "")
        target = pick(node.type == "delete_statement", lambda: node, lambda: _field(node, field))
        target_nodes = pick(target is None, tuple, lambda: walk(target))
        names_on_target = filter(lambda child: child.type == "identifier" and child.text == b"__all__", target_nodes)
        bound = any(
            child == target or child.parent.type in pattern_kinds
            or (child.parent.type in {"subscript", "attribute"} and child == child.parent.named_children[0])
            or child.parent.type in {"as_pattern_target", "delete_statement"}
            for child in names_on_target
        )
        imported = filter(
            lambda child: node.type in {"import_statement", "import_from_statement"}
            and child != _field(node, "module_name") and child.type != "comment",
            node.named_children,
        )
        rebound = any(_text(_field(child, "alias") or child).split(".", 1)[0] == "__all__" for child in imported)
        mutated = node.type == "call" and _text(_field(node, "function")) in mutations
        writes += bool(bound or rebound or mutated)
    literal = not root.has_error and assigned is not None and assigned.type == "list"
    match literal and writes == 1:
        case False:
            return None

    names = set()
    valid = True
    for entry in filter(lambda node: node.type != "comment", assigned.named_children):
        valid = valid and entry.type in {"string", "concatenated_string"}
        tokens = pick(entry.type == "concatenated_string", lambda: entry.named_children, lambda: (entry,))
        parts = []
        for token in filter(lambda node: node.type == "string", tokens):
            opening, *_, closing = token.named_children
            prefix = opening.text.lower().rstrip(b"\"'")
            valid = valid and prefix in {b"", b"r", b"u"}
            escapes = list(filter(lambda node: prefix != b"r" and node.type == "escape_sequence", walk(token)))
            bounds = [opening.end_byte, *(point for escape in escapes for point in (escape.start_byte, escape.end_byte)), closing.start_byte]
            raw = [source[start:end] for start, end in zip(bounds[::2], bounds[1::2], strict=True)]
            decoded = [codecs.decode(escape.text, "unicode_escape", "ignore") for escape in escapes]
            valid = valid and all(value or escape.text == b"\\\n" for escape, value in zip(escapes, decoded, strict=True))
            valid = valid and (prefix == b"r" or not any(re.search(rb"\\[xuUN]", chunk) for chunk in raw))
            literals = [chunk.decode("utf-8", "surrogateescape") for chunk in raw]
            valid = valid and not any(0xDC80 <= ord(character) <= 0xDCFF for chunk in literals for character in chunk)
            parts.append("".join(literal + value for literal, value in zip(literals, [*decoded, ""], strict=True)))
        names.add("".join(parts))
    return choose(valid, names, None)


def _undeclared_diag(code_functions, anchor, name):
    entry = read_or(code_functions, name, None)
    return pick(
        entry is not None,
        lambda: diagnostic(entry["ctx"], "HC-REF005", "error", f"{name} is exported by the module and declared in no .hd", entry["fdef"]),
        lambda: _ref005_diag(anchor, name),
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


# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names resolves a same-package from-import to its public alias -> test=python/honest-check/conformance/probe_exported_exception_names_alias.py::probe_exported_exception_names_alias
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names recognizes explicit and builtin type exception classes -> test=python/honest-check/conformance/probe_exported_exception_names_classes.py::probe_exported_exception_names_classes
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names excludes unresolved and non-exception bindings -> test=python/honest-check/conformance/probe_exported_exception_names_unverified.py::probe_exported_exception_names_unverified
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names requires one byte-identical Python initializer for from-imports -> test=python/honest-check/conformance/probe_exported_exception_names_verified_origin.py::probe_exported_exception_names_verified_origin
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names uses supplied initializer bytes for direct bindings -> test=python/honest-check/conformance/probe_exported_exception_names_authoritative_bytes.py::probe_exported_exception_names_authoritative_bytes
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names follows only one same-package import hop -> test=python/honest-check/conformance/probe_exported_exception_names_one_hop.py::probe_exported_exception_names_one_hop
# hd: exported_exception_names
def exported_exception_names(sources, export_source):
    """Verify direct exception bindings and a single same-package from-import."""
    advertised = _exported_names(export_source)
    python_sources = {
        Path(source["path"]): source["text"]
        for source in filter(lambda source: source["path"].endswith(".py"), sources)
    }
    origins = set(
        Path(source["path"])
        for source in filter(
            lambda source: Path(source["path"]).name == "__init__.py" and source["text"] == export_source,
            sources,
        )
    )
    verified_origin = len(origins) == 1
    initializer = pick(verified_origin, lambda: next(iter(origins)), lambda: Path("__init__.py"))
    python_sources[initializer] = export_source or b""
    package = initializer.parent
    builtin_exceptions = {
        name for name, _ in filter(lambda pair: inspect.isclass(pair[1]) and issubclass(pair[1], BaseException), vars(builtins).items())
    }
    package_bindings = {}
    binding_nodes = {
        "class_definition", "assignment", "augmented_assignment", "function_definition",
        "decorated_definition", "import_statement", "import_from_statement",
    }
    for path, source in filter(lambda item: bool(advertised), python_sources.items()):
        root = build_context(source, str(path), {})["root"]
        bindings = {}
        statements = map(
            lambda statement: pick(
                statement.type == "expression_statement",
                lambda: next(iter(statement.named_children), statement),
                lambda: statement,
            ),
            root.named_children,
        )
        for node in filter(lambda item: item.type in binding_nodes, statements):
            candidates = {}
            unshadowed_bases = builtin_exceptions - bindings.keys()
            match node.type:
                case "class_definition":
                    name = _text(_field(node, "name"))
                    bases = _field(node, "superclasses")
                    base_nodes = pick(bases is None, tuple, lambda: bases.named_children)
                    direct_exception = any(_text(base) in unshadowed_bases for base in base_nodes)
                    candidates[name] = choose(direct_exception, "exception", None)
                case "assignment" | "augmented_assignment":
                    target = _field(node, "left")
                    name = _text(target)
                    value = _field(node, "right")
                    direct = node.type == "assignment" and value is not None
                    constructor = direct and value.type == "call" and "type" not in bindings
                    constructor = constructor and _text(_field(value, "function")) == "type"
                    args = pick(constructor, lambda: _field(value, "arguments").named_children, tuple)
                    bases = pick(len(args) == 3 and args[1].type == "tuple", lambda: args[1].named_children, tuple)
                    direct_exception = bool(bases) and all(_text(base) in unshadowed_bases for base in bases)
                    candidates[name] = choose(direct_exception, "exception", None)
                case "function_definition" | "decorated_definition":
                    definition = pick(node.type == "decorated_definition", lambda: _field(node, "definition"), lambda: node)
                    candidates[_text(_field(definition, "name"))] = None
                case _:
                    module_node = _field(node, "module_name")
                    imports = filter(lambda child: child != module_node and child.type != "comment", node.named_children)
                    for imported in imports:
                        aliased = imported.type == "aliased_import"
                        original = _text(pick(aliased, lambda: _field(imported, "name"), lambda: imported))
                        public = pick(aliased, lambda: _text(_field(imported, "alias")), lambda: original.split(".")[0])
                        origin = choose(
                            verified_origin and path == initializer and module_node is not None,
                            (_text(module_node), original),
                            None,
                        )
                        candidates[public] = origin
            for name, conclusion in candidates.items():
                bindings[name] = choose(name in bindings, None, conclusion)
        package_bindings[path] = bindings

    verified = set()
    initializer_bindings = read_or(package_bindings, initializer, {})
    for public in advertised or ():
        match initializer_bindings.get(public):
            case "exception":
                verified.add(public)
            case (module, original):
                parts = module.split(".")
                within_package = parts[0] in {"", package.name} and all(parts[1:])
                target = package.joinpath(*parts[1:])
                candidates = [
                    path for path in filter(
                        lambda path: within_package and path != initializer and path in package_bindings,
                        (target / "__init__.py", target.parent / f"{target.name}.py"),
                    )
                ]
                evidence = pick(len(candidates) == 1, lambda: package_bindings[candidates[0]].get(original), lambda: None)
                verified.update(choose(evidence == "exception", (public,), ()))
    return verified


# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration -> test=python/honest-check/conformance/probe_cross_declaration.py::probe_cross_declaration
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration accepts a verified raised exception export without function arity -> test=python/honest-check/conformance/probe_cross_declaration_exception_raised.py::probe_cross_declaration_exception_raised
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration requires a verified exception export to be named in raises -> test=python/honest-check/conformance/probe_cross_declaration_exception_unraised.py::probe_cross_declaration_exception_unraised
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration keeps findings for unresolved exports and ordinary functions despite raises -> test=python/honest-check/conformance/probe_cross_declaration_unverified_raises.py::probe_cross_declaration_unverified_raises
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration reports a supplied initializer with no export list -> test=python/honest-check/conformance/probe_cross_declaration_missing_export_list.py::probe_cross_declaration_missing_export_list
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration reports a supplied initializer with a computed export list -> test=python/honest-check/conformance/probe_cross_declaration_computed_export_list.py::probe_cross_declaration_computed_export_list
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration preserves arity findings when the export list is invalid -> test=python/honest-check/conformance/probe_cross_declaration_invalid_export_arity.py::probe_cross_declaration_invalid_export_arity
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration uses a synthetic label for an invalid initializer without a known path -> test=python/honest-check/conformance/probe_cross_declaration_synthetic_export_location.py::probe_cross_declaration_synthetic_export_location
# hd: cross_declaration
def cross_declaration(sources, declaration, export_source, rule_ids):
    """Cross one module's .hd against the whole package, running only the crossing
    rules named in rule_ids (all five when empty) (§2.1)."""
    active = choose(len(rule_ids) == 0, _CROSSING_RULES, set(rule_ids))
    code_functions = _code_functions(sources)

    findings = (
        pick("HC-R003" in active, lambda: _per_function_rule(_r003_one, declaration, code_functions), lambda: [])
        + pick("HC-R004" in active, lambda: _per_function_rule(_r004_one, declaration, code_functions), lambda: [])
        + pick("HC-R005" in active, lambda: _per_function_rule(_r005_one, declaration, code_functions), lambda: [])
        + pick("HC-R002" in active, lambda: _r002(declaration, code_functions), lambda: [])
    )
    match "HC-REF005" in active:
        case False:
            return findings
    declared = {function["name"]: function for function in declaration["functions"]}
    raised = {name for function in declared.values() for name in read_or(function, "raises", [])}
    exports = _exported_names(export_source)
    exceptions = pick(bool(exports), lambda: exported_exception_names(sources, export_source), set)
    undeclared = (exports or set()) - exceptions - declared.keys()
    unraised = exceptions - raised
    anchor = _first_ctx(sources)
    match exports:
        case None:
            paths = [(Path(source["path"]), source["text"]) for source in sources]
            origins = {path for path, _ in filter(lambda item: item[0].name == "__init__.py" and item[1] == export_source, paths)}
            package_roots = pick(
                anchor is None,
                tuple,
                lambda: Path(anchor["path"]).parents,
            )
            shared_roots = filter(lambda root: all(root in path.parents for path, _ in paths), package_roots)
            location = pick(
                len(origins) == 1,
                lambda: str(next(iter(origins))),
                lambda: str(next(shared_roots, "__init__.py")),
            )
            findings.append(_reference_diagnostic(
                "HC-REF005", {"path": location}, "the package initializer requires one literal export list in __all__",
            ))
    findings.extend(pick(
        anchor is not None,
        lambda: [_undeclared_diag(code_functions, anchor, name) for name in sorted(undeclared)]
        + [
            _reference_diagnostic(
                "HC-REF005", anchor,
                f"{name!r} is an exported exception named in no .hd raises clause",
            )
            for name in sorted(unraised)
        ],
        list,
    ))
    for name in sorted((declared.keys() & code_functions.keys()) - exceptions):
        entry = code_functions[name]
        declared_arity = len(declared[name]["params"])
        parameters = _field(entry["fdef"], "parameters")
        separators = {"comment", "positional_separator", "keyword_separator"}
        actual_arity = sum(node.type not in separators for node in parameters.named_children)
        message = f"{name!r} is declared with {declared_arity} parameters and defined with {actual_arity}"
        findings.extend(pick(
            actual_arity != declared_arity,
            lambda: [diagnostic(entry["ctx"], "HC-REF005", "error", message, entry["fdef"])],
            list,
        ))
    return findings


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


# A dispatch table is a node in the reach graph, keyed by its own name under this
# prefix. A ':' cannot occur in a Python identifier, so a table node never collides
# with a function node (§HC-R001, P16).
_DISPATCH_NODE = "dispatch:"


def _referenced_names_in(ctx, fdef):
    identifiers = filter(lambda n: n.type == "identifier", walk(fdef))
    return set(n.text.decode("utf-8") for n in identifiers)


def _module_level_assignments(ctx):
    top = ctx["root"].named_children
    statements = filter(lambda s: s.type == "expression_statement", top)
    inner = map(lambda s: next(iter(s.named_children), None), statements)
    return filter(lambda a: a is not None and a.type == "assignment", inner)


def _dict_function_values(dict_node, names):
    # The function-name values a dict literal dispatches to: each pair value that is
    # a bare identifier naming a known top-level function. A lambda or spread value
    # names no function and contributes nothing.
    pairs = filter(lambda c: c.type == "pair", dict_node.named_children)
    values = map(lambda p: _field(p, "value"), pairs)
    idents = filter(lambda v: v is not None and v.type == "identifier", values)
    return set(v.text.decode("utf-8") for v in idents) & names


def _dispatch_tables(sources, names):
    # Each module-scope name bound to a dict literal, mapped to the subset of its
    # values that name known functions (§HC-R001, P16). The table is reached when a
    # reachable function references its name (see _call_graph); reaching it reaches
    # the function-name values it dispatches to. A dict nothing references never
    # becomes reachable, so its values stay orphans.
    tables = {}
    for source in sources:
        ctx = build_context(source["text"], source["path"], {})
        for assignment in _module_level_assignments(ctx):
            left = _field(assignment, "left")
            right = _field(assignment, "right")
            named = bool(
                left is not None and left.type == "identifier"
                and right is not None and right.type == "dictionary"
            )
            name = pick(named, lambda: left.text.decode("utf-8"), lambda: None)
            values = pick(named, lambda: _dict_function_values(right, names), lambda: set())
            tables.update(pick(
                name is not None and len(values) > 0,
                lambda: {name: read_or(tables, name, set()) | values},
                lambda: {},
            ))
    return tables


def _call_graph(entries, tables):
    names = set(e["name"] for e in entries)
    table_names = set(tables)
    graph = {}
    for entry in entries:
        called = _called_names_in(entry["ctx"], entry["fdef"]) & names
        referenced = _referenced_names_in(entry["ctx"], entry["fdef"]) & table_names
        graph[entry["name"]] = called | set(_DISPATCH_NODE + t for t in referenced)
    for table_name, values in tables.items():
        graph[_DISPATCH_NODE + table_name] = values
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


def _emit_orphans(sources, entries, roled):
    tables = _dispatch_tables(sources, set(e["name"] for e in entries))
    reachable = _reachable(roled, _call_graph(entries, tables))
    orphans = filter(lambda e: e["name"] not in reachable, entries)
    return [
        diagnostic(e["ctx"], "HC-R001", "error", "orphan function: no role, not reachable", e["fdef"])
        for e in orphans
    ]


def check_roles(sources, declaration):
    """Run the whole-program orphan rule HC-R001: a top-level function neither roled
    nor reachable from the roled set is an orphan; with no roles adopted the rule
    stands down (§HC-R001). Reachability follows a dispatch table: a reachable
    function that references a module-scope dispatch dict by name reaches the
    function-name values that dict dispatches to, so a handler invoked only through
    the table is reached, not orphaned (§HC-R001, P16)."""
    entries = _role_entries(sources)
    roled = _roled_names(entries, declaration)
    return pick(len(roled) == 0, lambda: [], lambda: _emit_orphans(sources, entries, roled))


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
