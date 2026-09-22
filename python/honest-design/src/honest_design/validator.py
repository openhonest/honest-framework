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


_UNIQUE_KINDS = ("functions", "types", "sets", "chains", "vocabularies", "envs", "stores")


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


# A side effect reaches a store by name when its target carries this prefix.
STORE_TARGET = "store:"


def _store_reads(module):
    """Every (function, store name) pair where a side effect names a store."""
    return [(f, se["target"][len(STORE_TARGET):])
            for f in module["functions"] for se in f["side_effects"]
            if se["target"].startswith(STORE_TARGET)]


def _store_of_impure(module):
    """A store holds the answers of a pure fn and nothing else. A boundary's answer comes from
    the world and can go stale; an orchestrator's answer is a sequence, not a value to keep."""
    roles = {f["name"]: f["role"] for f in module["functions"]}
    return [
        fault("store_of_impure", f"Store '{st['name']}' holds the answers of '{st['fn']}', which is not a pure fn; only a pure function's answer can be held without going stale", "server", {"store": st["name"], "fn": st["fn"]})
        for st in module["stores"]
        if roles.get(st["fn"]) != "fn"
    ]


def _unknown_stores(module):
    """Every side effect naming a store names a declared one (the dual of unknown_env)."""
    declared = {st["name"] for st in module["stores"]}
    return [
        fault("unknown_store", f"Function '{f['name']}' reaches store '{name}', which no store declares", "client", {"function": f["name"], "store": name})
        for f, name in _store_reads(module)
        if name not in declared
    ]


def _store_not_orchestrator(module):
    """Only an orchestrator reaches a store: it is the thing that keeps what each step returned.
    A pure fn reaching one is already impure; a boundary reaching one has confused the world
    with the process's own memory."""
    return [
        fault("store_not_orchestrator", f"Function '{f['name']}' reaches store '{name}', and it is a {f['role']}; only an orchestrator keeps what a step returned", "server", {"function": f["name"], "store": name})
        for f, name in _store_reads(module)
        if f["role"] not in ("orchestrator", "fn")
    ]


# --- the I/O surface: every side of the world a boundary touches is on a declared list ---------

_INPUT_ROLES = ("boundary_in", "reader")
_READS = ("reads", "reads_writes")
_WRITES = ("writes", "reads_writes")
# Targets closed by their own declarations, outside the inputs and outputs lists.
_OWN = (ENV_TARGET, STORE_TARGET)


def _world_targets(f, directions):
    """The sides of the world a function's side effects touch in the given directions, leaving
    out env: and store: targets, which their own declarations close."""
    return [se["target"] for se in f["side_effects"]
            if se["direction"] in directions and not se["target"].startswith(_OWN)]


def _boundaries(module):
    return [f for f in module["functions"] if f["role"] in _INPUT_ROLES + ("boundary_out",)]


def _surface_undeclared(module):
    """A module with boundaries and no inputs or outputs list has an open surface: one fault for
    the module, not one per boundary, because the fix is one declaration."""
    if _boundaries(module) and not module["surface_declared"]:
        n = len(_boundaries(module))
        return [fault("surface_undeclared", f"Module '{module['name']}' has {n} boundar{'y' if n == 1 else 'ies'} and declares no inputs or outputs, so its surface is open", "client", {"module": module["name"]})]
    return []


def _surface_unknown(module):
    """Every side a boundary reads is in inputs and every side it writes is in outputs; a
    reads_writes side is in both. Only checked once the module declares a surface at all."""
    if not module["surface_declared"]:
        return []
    ins = {m["value"] for m in module["inputs"]}
    outs = {m["value"] for m in module["outputs"]}
    faults = []
    for f in _boundaries(module):
        for t in _world_targets(f, _READS):
            if t not in ins:
                faults.append(fault("surface_unknown", f"Function '{f['name']}' reads '{t}', which inputs does not list", "client", {"function": f["name"], "target": t, "side": "inputs"}))
        for t in _world_targets(f, _WRITES):
            if t not in outs:
                faults.append(fault("surface_unknown", f"Function '{f['name']}' writes '{t}', which outputs does not list", "client", {"function": f["name"], "target": t, "side": "outputs"}))
    return faults


def _surface_unused(module):
    """A listed side no boundary touches is a stale declaration. Only once the module has a
    boundary, so a skeleton written surface-first is not a fault while its boundaries arrive."""
    if not _boundaries(module):
        return []
    read = {t for f in _boundaries(module) for t in _world_targets(f, _READS)}
    written = {t for f in _boundaries(module) for t in _world_targets(f, _WRITES)}
    faults = [fault("surface_unused", f"inputs lists '{m['value']}', which no boundary reads", "client", {"side": "inputs", "target": m["value"]})
              for m in module["inputs"] if m["value"] not in read]
    faults += [fault("surface_unused", f"outputs lists '{m['value']}', which no boundary writes", "client", {"side": "outputs", "target": m["value"]})
               for m in module["outputs"] if m["value"] not in written]
    return faults


def _boundary_without_surface(module):
    """A boundary touches a side of the world, or it is not a boundary: a door or reader reads
    something, an output boundary writes something. The environment is the world, so a reader
    of nothing but env: variables reads."""
    faults = []
    for f in _boundaries(module):
        reads = [se for se in f["side_effects"] if se["direction"] in _READS and not se["target"].startswith(STORE_TARGET)]
        if f["role"] in _INPUT_ROLES and not reads:
            faults.append(fault("boundary_without_surface", f"Function '{f['name']}' is a {f['role']} that reads nothing; a boundary touches a side of the world", "server", {"function": f["name"]}))
        if f["role"] == "boundary_out" and not _world_targets(f, _WRITES):
            faults.append(fault("boundary_without_surface", f"Function '{f['name']}' is a boundary_out that writes nothing; a boundary that only reads is a reader", "server", {"function": f["name"]}))
    return faults


def _door_takes_readable(module):
    """A door does not take what the module can read for itself: a parameter whose declared type
    a reader in the module returns lets a caller hand the module a second truth."""
    declared = {t["name"] for t in module["types"]} | {v["name"] for v in module["vocabularies"]}
    readable = {a["name"] for f in module["functions"] if f["role"] == "reader" for a in f["ret"]} & declared
    return [
        fault("door_takes_readable", f"Door '{f['name']}' takes a {a['name']}, which a reader in this module returns; the module can read it for itself", "server", {"function": f["name"], "type": a["name"]})
        for f in module["functions"] if f["role"] == "boundary_in"
        for p in f["params"] for a in p["type"] if a["name"] in readable
    ]


def _unawaited_caller(module):
    """An awaited callee makes its caller awaited too, along every call whose answer comes back:
    an invokes, each handler of an invoked dispatch table, each chain link to the next, out to
    the door, whose caller is the world and awaits it. The same edges a fault travels, because
    the promise carries the fault inside it. A caller left unmarked is a call somebody will
    write wrong, and the sign is a warning on a later line naming neither function.

    A pure fn may carry the word: it then awaits what it is handed, as honest-type's
    execute_chain_async awaits the links it is given. Nothing about waiting touches the world,
    so the word says nothing about purity, and whether the code is in fact async is
    honest-check HC-R003's question, not this one's."""
    awaited = {f["name"] for f in module["functions"] if f["awaited"]}
    return [
        fault("unawaited_caller", f"Function '{caller}' calls '{callee}', which must be awaited, and is not itself awaited", "server", {"function": caller, "callee": callee})
        for caller, callee in _callees(module)
        if callee in awaited and caller not in awaited
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
    _unawaited_caller,
    _door_called,
    _reader_calls,
    _store_of_impure,
    _unknown_stores,
    _store_not_orchestrator,
    _surface_undeclared,
    _surface_unknown,
    _surface_unused,
    _boundary_without_surface,
    _door_takes_readable,
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
