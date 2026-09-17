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


_UNIQUE_KINDS = ("functions", "types", "sets", "chains", "vocabularies", "envs")


def _duplicate_names(module):
    """Names are unique within each declaration kind (duals of HC004/HC005/HC006)."""
    faults = []
    for kind in _UNIQUE_KINDS:
        seen = set()
        for name in [d["name"] for d in module[kind]]:
            faults += [fault("duplicate_name", f"Duplicate {kind[:-1]} name '{name}'", "client", {"kind": kind, "name": name})] if name in seen else []
            seen.add(name)
    return faults


# A side effect reads the environment by name when its target carries this prefix.
ENV_TARGET = "env:"


def _env_reads(module):
    """Every (function, variable name) pair where a side effect reads the environment by name."""
    return [(f, se["target"][len(ENV_TARGET):])
            for f in module["functions"] for se in f["side_effects"]
            if se["target"].startswith(ENV_TARGET)]


def _unknown_envs(module):
    """Every environment read names a declared `env` (the configuration dual of unknown_link).

    A read that names no declaration is configuration nobody wrote down: the deployment must
    supply it and nothing in the file says so.
    """
    declared = {e["name"] for e in module["envs"]}
    return [
        fault("unknown_env", f"Function '{f['name']}' reads environment variable '{name}', which no env declares", "client", {"function": f["name"], "env": name})
        for f, name in _env_reads(module)
        if name not in declared
    ]


# The scalar that means "held, never read": an opaque reference to something outside the
# process, a driver connection or a file, obtained from a boundary and handed back to boundaries.
HANDLE = "handle"


def _type_names(parts):
    """Every type name an expression mentions, at any depth: list<Connection> names both."""
    names = set()
    for part in parts:
        names.add(part["name"])
        for arg in part["args"]:
            names |= _type_names(arg)
    return names


def _reaches_handle(name, aliases, budget):
    """Whether a name is the handle scalar, or an alias that leads to it within `budget` steps.

    The budget is the number of aliases in the module, so a chain can be as long as the module
    allows and a cycle of aliases, which leads nowhere, ends when the budget does."""
    if name == HANDLE:
        return True
    if budget == 0 or name not in aliases:
        return False
    return any(_reaches_handle(a["name"], aliases, budget - 1) for a in aliases[name])


def _handles(module):
    """The names that mean a handle: the scalar, and every alias that resolves to it."""
    aliases = {t["name"]: t["alias"] for t in module["types"] if t["alias"]}
    return {HANDLE} | {name for name in aliases if _reaches_handle(name, aliases, len(aliases))}


def _held_not_read(module):
    """A handle is held and passed to a boundary, never read.

    `any` used to carry this meaning beside its other one, a type nobody has decided, and the two
    looked alike. A pure function that names a handle in its own signature has opened it; carrying
    one inside a record it takes is holding, and is allowed.
    """
    handles = _handles(module)
    faults = []
    for f in module["functions"]:
        if f["role"] != "fn":
            continue
        named = _type_names(f["ret"])
        for p in f["params"]:
            named |= _type_names(p["type"])
        for h in sorted(named & handles):
            faults.append(fault("handle_read", f"Pure function '{f['name']}' names the handle '{h}' in its signature; a handle is held and passed to a boundary, never read", "server", {"function": f["name"], "handle": h}))
    return faults


# The name of the value a function returns when it cannot do what it was asked.
FAULT = "Fault"


def _can_fault(module):
    """The functions whose return type says they can fail."""
    return {f["name"] for f in module["functions"] if FAULT in _type_names(f["ret"])}


def _callees(module):
    """Every (caller, callee) pair whose answer comes back to the caller: an invoke, each handler
    of an invoked dispatch table, and each link of a chain to the next. A pair that is both invoked
    and chained is one call, so it appears once."""
    tables = {d["name"]: [e["handler"] for e in d["entries"]] for d in module["dispatches"]}
    pairs = []
    for f in module["functions"]:
        for target in f["invokes"]:
            pairs += [(f["name"], callee) for callee in tables.get(target, [target])]
    for c in module["chains"]:
        pairs += list(zip(c["links"], c["links"][1:]))
    return list(dict.fromkeys(pairs))


def _fault_swallowed(module):
    """A fault bubbles up through returns: as the return value of each function, back through
    its callers, out to the boundary. Never a log line, never an exception past the signatures,
    never a flag on something shared. So if a callee's return says it can fault, its caller's
    return must say so too. A caller invoking a dispatch table inherits every handler's answer,
    because it cannot know which one ran."""
    fails = _can_fault(module)
    return [
        fault("fault_swallowed", f"Function '{caller}' calls '{callee}', which can fault, and cannot return one", "server", {"function": caller, "callee": callee})
        for caller, callee in _callees(module)
        if callee in fails and caller not in fails
    ]


def _fault_shape(module):
    """A fault is never cryptic: it tells the programmer what went wrong and what to do instead.
    The words are not checkable, but the shape is: a module whose functions can fault declares
    Fault as a record with fields to say it in, not as an alias or a bare name."""
    declared = {t["name"]: t for t in module["types"]}
    # A Fault declared elsewhere has its shape checked there.
    thin = bool(_can_fault(module)) and FAULT in declared and len(declared[FAULT]["record"]) < 2
    return [fault("fault_shape", "Fault is declared without the fields to say what went wrong and what to do instead", "server", {"type": FAULT})] if thin else []


def _door_called(module):
    """A door is where the world calls in, and nothing inside the module calls one: no invokes
    names it, and it is never a chain link after the first. A read the program initiates, a clock,
    a file it chose to open, is a reader, and declaring it a door tells the truth about the column
    and a lie about the arrows."""
    doors = {f["name"] for f in module["functions"] if f["role"] == "boundary_in"}
    return [
        fault("door_called", f"Function '{caller}' calls '{callee}', a door; the world calls a door, nothing inside does. A read the program asks for is a reader", "server", {"function": caller, "callee": callee})
        for caller, callee in _callees(module)
        if callee in doors
    ]


def _reader_calls(module):
    """A reader answers the program and asks nothing of it: it invokes nothing and heads no chain."""
    readers = {f["name"] for f in module["functions"] if f["role"] == "reader"}
    return [
        fault("reader_calls", f"Reader '{caller}' calls '{callee}'; a reader answers the program and asks nothing of it", "server", {"function": caller, "callee": callee})
        for caller, callee in _callees(module)
        if caller in readers
    ]


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
    _unknown_envs,
    _duplicate_names,
    _impure_pure_functions,
    _held_not_read,
    _fault_swallowed,
    _fault_shape,
    _door_called,
    _reader_calls,
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
