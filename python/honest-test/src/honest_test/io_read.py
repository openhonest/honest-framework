"""The readers (spec section 11, section 3.6) and the pure config resolver.

read_source pulls one file's text; read_config decodes honest-test.toml; load_under_test imports
each module under src/ to obtain its live declarations. resolve_supplied_config is the pure
reshape HC-R006 moves out of the config reader.
"""

import importlib.util
import tomllib
from pathlib import Path

from honest_type.chains import is_link, link_meta


def read_source(path):
    """Pull one source file's complete text from disk and return it as a string (spec section
    11). Its one side effect is reading the filesystem."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def read_config(path):
    """Read honest-test.toml and decode it to the plain parsed table (spec sections 3.6, 10). The
    table is empty when no file exists; the standard-format decode is the door's one carve-out
    (HC-R006). Its one side effect is reading the filesystem."""
    if not Path(path).exists():
        return {}
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def resolve_supplied_config(table):
    """Resolve the decoded predicates table into the supplied-values record the generators take
    (spec sections 3.6, 10): a map from predicate name to its valid list, invalid list and
    strategy. The empty map when no predicate is declared. Reads no world, returns pure data."""
    resolved = {}
    for name, entry in table.items():
        resolved[name] = {
            "valid": list(entry.get("valid", [])),
            "invalid": list(entry.get("invalid", [])),
            "strategy": entry["strategy"] if "strategy" in entry else "supplied_only",
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
    return hasattr(value, "get") and "states" in value and "transitions" in value and "events" in value


def _is_schema(value):
    return hasattr(value, "get") and "tables" in value


def _is_component(value):
    return hasattr(value, "get") and "template" in value and "routes" in value


def _is_provider(value):
    return hasattr(value, "get") and "resolve_actor" in value and "actor_recognizer" in value


def _is_gate(value):
    return hasattr(value, "get") and "name" in value and "location" in value and "proof" in value


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
            if is_link(value):
                live["links"].append(value)
                meta = link_meta(value)
                accepts = meta.get("accepts")
                if accepts is not None and accepts not in live["vocabularies"]:
                    live["vocabularies"].append(accepts)
                binds = meta.get("binds")
                if binds is not None and binds not in live["bindings"]:
                    live["bindings"].append(binds)
            elif _is_machine(value) and value not in live["machines"]:
                live["machines"].append(value)
            elif _is_schema(value) and value not in live["schemas"]:
                live["schemas"].append(value)
            elif _is_component(value) and value not in live["components"]:
                live["components"].append(value)
            elif _is_provider(value) and value not in live["providers"]:
                live["providers"].append(value)
            elif _is_gate(value) and value not in live["gates"]:
                live["gates"].append(value)
    return live
