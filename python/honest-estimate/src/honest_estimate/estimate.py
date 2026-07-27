"""Deductive size from the .hd contract boundary (honest-estimate-architecture.md §6.1, §6.2).

Reads the declared surface — not the code — and emits the two deductive size numbers: breadth (the
count of elementary processes) and depth (bits of specified case-distinction over closed vocabularies).
Pure over the .hd IR; the one boundary is read_hd, itself pure over the source string. The inductive
numbers (effort, defects, mutation density) are not emitted here — this leaf is the declaration-time,
deductive half (§10).
"""

from math import log2

from honest_design import read_hd
from honest_design.result import err, fault, ok

# §7.1 — a module's boundary contracts. A boundary/orchestrator role is a contract by declaration; a
# pure `fn` no sibling invokes is a module-boundary contract reached from outside. A pure `fn` a
# sibling invokes is an interior helper, covered by its caller (§7.2), and is not a process.
_BOUNDARY_ROLES = frozenset({"boundary_in", "boundary_out", "orchestrator"})


def elementary_processes(module):
    """The names of `module`'s elementary processes, sorted (§7.1). Widened rule: a boundary or
    orchestrator role, or a pure `fn` no sibling invokes."""
    invoked = {name for f in module["functions"] for name in f["invokes"]}
    return sorted(
        f["name"]
        for f in module["functions"]
        if f["role"] in _BOUNDARY_ROLES or f["name"] not in invoked
    )


def _routed_targets(module):
    """The functions reached from the input boundary — a route or an entry targets them. These are
    the user-facing transactions, the IFPUG-countable subset of the processes (§6.1)."""
    return {r["target"] for r in module["routes"]} | {e["target"] for e in module["entries"]}


def breadth(module):
    """The breadth number (§6.1): the process count, split into the IFPUG-countable subset (user-
    facing transactions reached from the input boundary) and the beyond-IFPUG internal/system rest,
    with the internal share. The split is provisional — ILF/EIF are not yet modelled (§15)."""
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
    }


def _param_type_name(param):
    """The head atom name of a parameter's declared type; '' when the type is empty."""
    atoms = param["type"]
    return atoms[0]["name"] if atoms else ""


def depth(module):
    """The depth number (§6.2, §7.3): bits of specified case-distinction over the processes' closed-
    vocabulary parameters. A parameter typed by a declared set contributes log-2 of its cardinality;
    a parameter of any other type is open — it contributes nothing and is flagged, never counted as
    raw cardinality (§7.3). Deductive only over closed vocabularies, which is why it is Honest-native."""
    cardinality = {s["name"]: len(s["members"]) for s in module["sets"]}
    processes = set(elementary_processes(module))
    bits = 0.0
    open_flags = []
    for f in module["functions"]:
        if f["name"] not in processes:
            continue
        for param in f["params"]:
            name = _param_type_name(param)
            card = cardinality.get(name)
            if card is None:
                open_flags.append({"process": f["name"], "param": param["name"], "type": name})
            else:
                bits += log2(card)
    return {"bits": bits, "open_flags": open_flags}


def size(source):
    """Read one .hd module's source and emit its deductive size (§13 `size`): breadth, depth bits, and
    the open-vocabulary flags, wrapped in the shared Result. A malformed source returns the read
    fault; a source that declares no module returns a `no_module` fault; neither is raised."""
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
            "processes": breadth(module),
            "bits_of_case_distinction": measured["bits"],
            "open_vocabulary_flags": measured["open_flags"],
        }
    )
