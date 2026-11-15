"""The import-alias resolver (§3.3, §3.5) and the per-file CheckContext builder
(§3.4). build_context assembles the one shared parse every rule reads; it parses
once, resolves aliases once, and hands the record to check_source."""

from honest_parse import language_of, parse, walk

from ._util import choose, pick, read_or
from .nodes import _field, _text

_FRAMEWORK_MODULES = {
    "honest_type", "honest_test", "honest_persist", "honest_dom", "honest_page",
    "honest_format", "honest_check", "honest_design", "honest_parse", "honest_auth",
    "honest_state", "honest_observe", "honest_components", "honest_compose",
}


def _from_one(imported):
    return choose(
        imported.type == "aliased_import",
        {_text(_field(imported, "alias")): _text(_field(imported, "name"))},
        {imported.text.decode("utf-8"): imported.text.decode("utf-8")},
    )


def _from_aliases(statement):
    module = _text(_field(statement, "module_name"))
    return pick(
        module not in _FRAMEWORK_MODULES,
        lambda: {},
        lambda: _collect_from_binds(statement),
    )


def _collect_from_binds(statement):
    module_node = _field(statement, "module_name")
    imports = filter(
        lambda c: c != module_node and c.type in {"aliased_import", "dotted_name"},
        statement.named_children,
    )
    out = {}
    for imported in imports:
        out.update(_from_one(imported))
    return out


def _aliased_module(node):
    name = _text(_field(node, "name"))
    alias = _text(_field(node, "alias"))
    return choose(name in _FRAMEWORK_MODULES, {f"{alias}.*": f"{name}.*"}, {})


def _plain_module(node):
    name = node.text.decode("utf-8")
    return choose(name in _FRAMEWORK_MODULES, {f"{name}.*": f"{name}.*"}, {})


def _import_one(node):
    return choose(node.type == "aliased_import", _aliased_module(node), _plain_module(node))


def _import_aliases(statement):
    out = {}
    for node in filter(
        lambda c: c.type in {"aliased_import", "dotted_name"}, statement.named_children
    ):
        out.update(_import_one(node))
    return out


def resolve_aliases(root, source):
    """The import-alias map from each local name a framework import bound to that
    import's canonical framework name (§3.3)."""
    nodes = walk(root)
    out = {}
    for statement in filter(lambda n: n.type == "import_from_statement", nodes):
        out.update(_from_aliases(statement))
    for statement in filter(lambda n: n.type == "import_statement", nodes):
        out.update(_import_aliases(statement))
    return out


def _resolve_min_run(rule_config):
    project = read_or(rule_config, "HC-OR003", {})
    return read_or(project, "min_run", 3)


def build_context(source, path, rule_config):
    """The one pure builder of the per-file CheckContext (§3.4): parse under the
    grammar the path selects, resolve aliases, walk the nodes, and merge the
    documented HC-OR003 min_run over the project's config."""
    language = read_or(language_of(path), "ok", "python")
    root = parse(source, language).root_node
    resolved = {**rule_config, "HC-OR003": {"min_run": _resolve_min_run(rule_config)}}
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": resolve_aliases(root, source),
        "roles": {},
        "source": source,
        "path": path,
        "rule_config": resolved,
    }
