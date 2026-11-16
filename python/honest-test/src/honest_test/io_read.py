"""The readers (spec section 11, section 3.6) and the pure config resolver.

read_source pulls one file's text; read_config decodes honest-test.toml; load_under_test imports
each module under src/ to obtain its live declarations. resolve_supplied_config is the pure
reshape HC-R006 moves out of the config reader.
"""

import importlib.util
import tomllib
from pathlib import Path

from honest_type.chains import is_link, link_meta

from honest_test._util import _pick, _read_or


def read_source(path):
    """Pull one source file's complete text from disk and return it as a string (spec section
    11). Its one side effect is reading the filesystem."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def read_config(path):
    """Read honest-test.toml and decode it to the plain parsed table (spec sections 3.6, 10). The
    table is empty when no file exists; the standard-format decode is the door's one carve-out
    (HC-R006). Its one side effect is reading the filesystem."""
    return _pick(
        Path(path).exists(),
        lambda: tomllib.loads(Path(path).read_text(encoding="utf-8")),
        lambda: {},
    )


def resolve_supplied_config(table):
    """Resolve the decoded predicates table into the supplied-values record the generators take
    (spec sections 3.6, 10): a map from predicate name to its valid list, invalid list and
    strategy. The empty map when no predicate is declared. Reads no world, returns pure data."""
    resolved = {}
    for name, entry in table.items():
        resolved[name] = {
            "valid": list(_read_or(entry, "valid", [])),
            "invalid": list(_read_or(entry, "invalid", [])),
            "strategy": _read_or(entry, "strategy", "supplied_only"),
        }
    return resolved


def _import_file(path, module_name):
    """Import one source file into the running interpreter, running its top-level code (the
    loader boundary, spec section 11)."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_machine(value):
    return isinstance(value, dict) and "states" in value and "transitions" in value and "events" in value


def _is_schema(value):
    return isinstance(value, dict) and "tables" in value


def _is_component(value):
    return isinstance(value, dict) and "template" in value and "routes" in value


def _is_provider(value):
    return isinstance(value, dict) and "resolve_actor" in value and "actor_recognizer" in value


def _is_gate(value):
    return isinstance(value, dict) and "name" in value and "location" in value and "proof" in value


# The non-link recognizers, in the priority order the classifier scans them (spec section 11):
# the first whose recognizer matches a not-yet-collected value owns it.
_KINDS = (
    (_is_machine, "machines"),
    (_is_schema, "schemas"),
    (_is_component, "components"),
    (_is_provider, "providers"),
    (_is_gate, "gates"),
)


def _handle_link(value, live):
    """Collect one link and the vocabulary and binding its declaration carries (spec section 11)."""
    live["links"].append(value)
    meta = link_meta(value)
    accepts = meta.get("accepts")
    _pick(
        accepts is not None and accepts not in live["vocabularies"],
        lambda: live["vocabularies"].append(accepts),
        lambda: None,
    )
    binds = meta.get("binds")
    _pick(
        binds is not None and binds not in live["bindings"],
        lambda: live["bindings"].append(binds),
        lambda: None,
    )


def _collect_other(value, live):
    """Collect one non-link value under the first recognizer that matches it and has not already
    collected it (spec section 11); a value no recognizer matches is collected nowhere."""
    matched = filter(lambda rk: rk[0](value) and value not in live[rk[1]], _KINDS)
    pair = next(matched, None)
    _pick(pair is None, lambda: None, lambda: live[pair[1]].append(value))


def _collect_value(value, live):
    """Route one module-level value to the link handler or the non-link classifier (spec section
    11); a link is recognized first, then the other kinds in _KINDS order."""
    _pick(is_link(value), lambda: _handle_link(value, live), lambda: _collect_other(value, live))


def load_under_test(src_dir):
    """Import each module under src_dir to obtain its live declarations (spec section 11): the
    links honest-type recognizes, the vocabularies read off their declared accepts, and the state
    machines, schemas, components, providers and gates declared at module level. Returns a
    LiveModules record. Its side effects are the filesystem, the import system and the
    honest-type.link_meta seam."""
    live = {
        "vocabularies": [], "bindings": [], "links": [], "chains": [], "machines": [],
        "schemas": [], "components": [], "providers": [], "gates": [],
    }
    for index, path in enumerate(sorted(Path(src_dir).rglob("*.py"))):
        module = _import_file(str(path), f"_hf_under_test_{index}_{path.stem}")
        for value in vars(module).values():
            _collect_value(value, live)
    return live
