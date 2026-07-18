"""The .hd validator: Module IR -> [fault].

Pure. An empty list is a valid module. The checks are the declaration-level duals of the structural
rules honest-check enforces on code (rules.hd): every intra-module reference resolves, names are
unique, and the pure-function boundary discipline holds. These are the faults honest-check's
conformance tier consumes to check code against its declaration.

Scope: everything decidable from ONE module's IR, and verified to raise nothing on the real .hd
corpus. Three rules are deliberately out of this per-module pass because they need context this
module does not carry, or because the corpus shows the rule as stated does not hold:

- unknown_type / unknown reference to a sibling module — a type or invoke may resolve in another
  module; deciding it needs the whole workspace, so it belongs to a document-level pass.
- unreachable_role — reachability spans dispatch handlers, boundary/orchestrator roots, cross-module
  invokes, and pure-helper call chains the .hd does not name; a per-module pass produces false
  positives on the real corpus, so this stays with honest-check's code-level HC-R001.
- orchestrator-carries-no-side-effect — the corpus has orchestrators that legitimately declare a
  side effect (honest-persist migrate/execute), so the rule as first drafted does not hold and is
  not enforced.
"""

from honest_design.result import fault


def _declared_functions(module):
    return {f["name"] for f in module["functions"]}


def _unknown_links(module):
    """Every chain link names a declared function (dual of HC001)."""
    declared = _declared_functions(module)
    return [
        fault("unknown_link", f"Chain '{c['name']}' references undeclared function '{link}'", "client", {"chain": c["name"], "link": link})
        for c in module["chains"]
        for link in c["links"]
        if link not in declared
    ]


def _unknown_targets(module):
    """Every route and entry targets a declared function (dual of HC001 for the input boundary)."""
    declared = _declared_functions(module)
    routes = [
        fault("unknown_target", f"Route '{r['method']} {r['path']}' targets undeclared function '{r['target']}'", "client", {"target": r["target"]})
        for r in module["routes"]
        if r["target"] not in declared
    ]
    entries = [
        fault("unknown_target", f"Entry '{e['callsite']}' targets undeclared function '{e['target']}'", "client", {"target": e["target"]})
        for e in module["entries"]
        if e["target"] not in declared
    ]
    return routes + entries


_UNIQUE_KINDS = ("functions", "types", "sets", "chains", "vocabularies")


def _duplicate_names(module):
    """Names are unique within each declaration kind (duals of HC004/HC005/HC006)."""
    faults = []
    for kind in _UNIQUE_KINDS:
        seen = set()
        for name in [d["name"] for d in module[kind]]:
            faults += [fault("duplicate_name", f"Duplicate {kind[:-1]} name '{name}'", "client", {"kind": kind, "name": name})] if name in seen else []
            seen.add(name)
    return faults


def _impure_pure_functions(module):
    """A pure `fn` declares no side effect — only a boundary may."""
    return [
        fault("impure_pure_function", f"Pure function '{f['name']}' declares a side effect", "server", {"function": f["name"]})
        for f in module["functions"]
        if f["role"] == "fn" and f["side_effects"]
    ]


_CHECKS = (
    _unknown_links,
    _unknown_targets,
    _duplicate_names,
    _impure_pure_functions,
)


def validate(module):
    """Validate a module's IR; return the list of faults (empty means valid)."""
    return [f for check in _CHECKS for f in check(module)]
