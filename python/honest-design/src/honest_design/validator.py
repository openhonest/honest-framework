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


def _callers_of(module, dispatch_name):
    """The functions that invoke a dispatch table. Their input is what the table projects from."""
    return [f for f in module["functions"] if dispatch_name in f["invokes"]]


def _record_fields(module):
    """Every declared record's fields, keyed by type name."""
    return {t["name"]: {fl["name"]: fl["type"] for fl in t["record"]} for t in module["types"] if t["record"]}


def _bad_surfaces(module):
    """Every surface id is unique within its block, and a block declares at least one.

    Order is not checked, and cannot be from one module's IR: the declaration is the order, so
    there is nothing here to compare it against. Whether a rendered page matches it is a
    cross-artifact question honest-check answers by resolving the template's ids against this
    block, as HC-REF001 resolves an action target against a mounted route.
    """
    faults = []
    for block in module["surfaces"]:
        here = {"surfaces": block["name"]}
        if not block["members"]:
            faults.append(fault("empty_surfaces", f"Surfaces block '{block['name']}' declares no surface. A page that renders none has no contract to state.", "client", here))
        seen = set()
        for member in block["members"]:
            if member["id"] in seen:
                faults.append(fault("duplicate_surface", f"Surfaces block '{block['name']}' declares '{member['id']}' more than once. An id names one element, so the order is ambiguous.", "client", {**here, "id": member["id"]}))
            seen.add(member["id"])
    return faults


def _bad_projections(module):
    """A dispatch entry's `from` names a real field of its caller's input, and the handler takes it.

    Without this the projection is a comment. It exists so a handler declares the slice it reads
    instead of the whole record, and a slice that names a field nobody has, or a handler whose
    parameter is a different type from the field it is fed, is the defect the notation was added
    to catch.
    """
    records, by_name = _record_fields(module), {f["name"]: f for f in module["functions"]}
    faults = []
    for table in module["dispatches"]:
        inputs = [a["name"] for c in _callers_of(module, table["name"]) for p in c["params"] for a in p["type"]]
        fields = {n: t for i in inputs if i in records for n, t in records[i].items()}
        for entry in table["entries"]:
            here = {"dispatch": table["name"], "key": entry["key"], "projection": entry["projection"]}
            if not entry["projection"]:
                continue
            if entry["projection"] not in fields:
                faults.append(fault("unknown_projection", f"Dispatch '{table['name']}' entry '{entry['key']}' projects '{entry['projection']}', which is not a field of its caller's input", "client", here))
                continue
            handler = by_name.get(entry["handler"])
            params = handler["params"] if handler else []
            if len(params) != 1 or params[0]["type"] != fields[entry["projection"]]:
                faults.append(fault("projection_mismatch", f"Dispatch '{table['name']}' entry '{entry['key']}' feeds '{entry['projection']}' to '{entry['handler']}', which does not take exactly that", "client", here))
    return faults


_CHECKS = (
    _bad_surfaces,
    _unknown_links,
    _unknown_targets,
    _duplicate_names,
    _impure_pure_functions,
    _bad_projections,
)


def validate(module):
    """Validate a module's IR; return the list of faults (empty means valid).

    This is a boundary and the caller supplies the IR, so the shape is checked here once. A
    document (what `read_hd` returns) holds modules rather than being one, and handing one over
    is the obvious first mistake: it is named here rather than surfacing as a KeyError from
    whichever check reads a field first."""
    if "modules" in module:
        return [fault("not_a_module", "validate takes one module's IR; this is a document. Pass each of its 'modules' in turn.", "client", {})]
    return [f for check in _CHECKS for f in check(module)]
