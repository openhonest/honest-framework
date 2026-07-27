"""Deductive SIZE from the .hd contract boundary (honest-estimate-architecture.md §6.1, §7.1, §7.2, §7.4).

Reads the declared surface — not the code — and emits the three deductive size readings, none fused:
VFP (the count of elementary processes, §7.1), COSMIC CFP (data movements, §7.2, an uncertified Honest
mapping), and depth (bits of specified case-distinction over closed vocabularies and composed types,
§6.1/§7.4). Pure over the .hd IR; read_hd is the one (pure) boundary. Cost, duration, and quality (the
measured and inductive dimensions) are not here — this leaf is the declaration-time, deductive half (§10).
"""

from math import log2

from honest_design import read_hd
from honest_design.result import err, fault, ok

# §7.1 — the boundary role is the authority. A boundary/orchestrator role IS an elementary process.
_BOUNDARY_ROLES = frozenset({"boundary_in", "boundary_out", "orchestrator"})


def _invoked_within(module):
    """Every function name some sibling in the module invokes (the interior of the call graph)."""
    return {name for f in module["functions"] for name in f["invokes"]}


def elementary_processes(module):
    """The names of `module`'s elementary processes, sorted (§7.1). The boundary role is the authority:
    where any function carries one, the processes are exactly the role-bearing functions. Only where a
    module declares no boundary/orchestrator role at all does the invoke-graph fallback apply — a pure
    function no sibling invokes is treated as a contract — and the module is then under-declared."""
    by_role = [f["name"] for f in module["functions"] if f["role"] in _BOUNDARY_ROLES]
    if by_role:
        return sorted(by_role)
    invoked = _invoked_within(module)
    return sorted(f["name"] for f in module["functions"] if f["name"] not in invoked)


def _under_declared(module):
    """True when the module has functions but no boundary/orchestrator role, so elementary_processes
    fell back to the invoke graph (§7.1). Surfaced, never hidden."""
    return bool(module["functions"]) and not any(f["role"] in _BOUNDARY_ROLES for f in module["functions"])


def _routed_targets(module):
    """The functions reached from the input boundary — a route or an entry targets them. The user-
    facing transactions, the IFPUG-countable subset of the processes (§6.1)."""
    return {r["target"] for r in module["routes"]} | {e["target"] for e in module["entries"]}


def vfp(module):
    """VFP breadth (§6.1, §7.1): the elementary-process count, split into the routed IFPUG-countable
    subset and the beyond-IFPUG internal rest, with the internal share, plus whether the count came
    from the role-graph fallback (under_declared). The split is provisional — ILF/EIF are not modelled."""
    processes = elementary_processes(module)
    routed = _routed_targets(module)
    ifpug = [name for name in processes if name in routed]
    total = len(processes)
    beyond = total - len(ifpug)
    return {
        "total": total,
        "ifpug_countable": len(ifpug),
        "beyond_ifpug_internal": beyond,
        "internal_share_ratio": beyond / total if total else 0.0,
        "under_declared": _under_declared(module),
    }


# §7.2 — the Honest boundary-role → COSMIC data-movement mapping (uncertified, see §15).
_MOVEMENT_BY_ROLE = {"boundary_in": 1, "boundary_out": 1, "orchestrator": 0, "fn": 0}
_MOVEMENT_BY_EFFECT = {"reads": 1, "writes": 1, "reads_writes": 2}
_CFP_FLOOR = 2


def _process_movements(f):
    """The data movements one process declares (§7.2): an Entry/eXit from its role, a Read/Write per
    side effect. COSMIC floors a functional process at two movements."""
    from_role = _MOVEMENT_BY_ROLE.get(f["role"], 0)
    from_effects = sum(_MOVEMENT_BY_EFFECT.get(se["direction"], 0) for se in f["side_effects"])
    return max(from_role + from_effects, _CFP_FLOOR)


def cfp(module):
    """COSMIC CFP (§7.2, Honest mapping, uncertified): the sum of data movements over every elementary
    process, each movement one CFP, each process floored at two."""
    functions = {f["name"]: f for f in module["functions"]}
    return sum(_process_movements(functions[name]) for name in elementary_processes(module))


def _cardinalities(module):
    """The closed cardinalities declared in the module: each set's member count, each vocabulary's
    (the sum of its referenced sets' cardinalities, since a classification lands in one state of one
    set), and each composed type's field list for recursion."""
    sets = {s["name"]: len(s["members"]) for s in module["sets"]}
    vocabs = {v["name"]: sum(sets.get(name, 0) for name in v["sets"]) for v in module["vocabularies"]}
    records = {t["name"]: t["record"] for t in module["types"] if t["record"]}
    return sets, vocabs, records


def _head_atom(type_atoms):
    """The head atom name of a declared type (its first atom); '' when the type is empty."""
    return type_atoms[0]["name"] if type_atoms else ""


def _bits_of(type_name, sets, vocabs, records, seen, process, path, open_flags):
    """Bits a single typed slot contributes (§6.1): log-2 of a set's or vocabulary's cardinality, or
    the sum over a composed type's fields (a product of cardinalities, so the log is the sum of logs),
    recursing. Any other type — a raw scalar, an unknown name, or a cycle — is open: it contributes
    nothing and is flagged (§7.4)."""
    if sets.get(type_name, 0) > 0:
        return log2(sets[type_name])
    if vocabs.get(type_name, 0) > 0:
        return log2(vocabs[type_name])
    if type_name in records and type_name not in seen:
        return sum(
            _bits_of(_head_atom(field["type"]), sets, vocabs, records, seen | {type_name}, process, f"{path}.{field['name']}", open_flags)
            for field in records[type_name]
        )
    open_flags.append({"process": process, "param": path, "type": type_name})
    return 0.0


def depth(module):
    """The depth reading (§6.1, §7.4): bits of specified case-distinction over the processes' input
    parameters, recursing into composed types. Inputs only — a deterministic contract distinguishes no
    more cases than its input partition admits, so the return type adds no depth."""
    sets, vocabs, records = _cardinalities(module)
    processes = set(elementary_processes(module))
    bits = 0.0
    open_flags = []
    for f in module["functions"]:
        if f["name"] not in processes:
            continue
        for param in f["params"]:
            bits += _bits_of(_head_atom(param["type"]), sets, vocabs, records, frozenset(), f["name"], param["name"], open_flags)
    return {"bits": bits, "open_flags": open_flags}


def size(source):
    """Read one .hd module's source and emit its deductive SIZE (§13 `size`): CFP, VFP, depth bits, and
    the open-vocabulary flags, wrapped in the shared Result. A malformed source returns the read fault;
    a source that declares no module returns a no_module fault; neither is raised. CFP is reported
    uncertified until the COSMIC mapping is validated (§7.2, §15)."""
    document = read_hd(source)
    if "err" in document:
        return document
    modules = document["ok"]["modules"]
    if not modules:
        return err(fault("no_module", "the .hd declares no module", "client", {}))
    module = modules[0]
    measured = depth(module)
    return ok(
        {
            "cosmic_cfp": cfp(module),
            "vfp": vfp(module),
            "bits_of_case_distinction": measured["bits"],
            "open_vocab_flags": measured["open_flags"],
            "cfp_certified": False,
        }
    )
