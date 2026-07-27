"""honest-estimate conformance: the generative proof.

Probes every branch of the three SIZE readings: the §7.1 role-authority process rule and its flagged
invoke-graph fallback, the VFP IFPUG split and zero-process ratio, the §7.2 CFP data-movement mapping
with its two-movement floor, the depth recursion over sets, vocabularies, and composed types with the
§7.4 open-parameter flagging and its cycle guard, and the size boundary's success and two fault paths.
Each probe returns a list of failures; run() aggregates.
"""

import math

import honest_estimate
from honest_estimate import cfp, depth, elementary_processes, size, vfp
from honest_estimate.estimate import (
    _bits_of,
    _cardinalities,
    _head_atom,
    _invoked_within,
    _process_movements,
    _routed_targets,
    _under_declared,
)

_HD_A = (
    'module m\n  layer tooling\n  set PAIR = { "a", "b" }\n  set QUAD = { "w", "x", "y", "z" }\n'
    '  boundary_in fn recognise : (raw: PAIR) -> str side_effect reads "store"\n'
    '  boundary_out fn emit : (v: QUAD) -> str side_effect writes "store"'
)
_HD_B = (
    'module m\n  layer tooling\n  set MODE = { "on", "off" }\n'
    "  boundary_in fn act : (mode: MODE, note: str) -> str"
)


def _module(functions=(), sets=(), vocabularies=(), types=(), routes=(), entries=()):
    return {
        "functions": list(functions),
        "sets": list(sets),
        "vocabularies": list(vocabularies),
        "types": list(types),
        "routes": list(routes),
        "entries": list(entries),
    }


def _fn(name, role="fn", invokes=(), params=(), side_effects=()):
    return {"name": name, "role": role, "invokes": list(invokes), "params": list(params), "side_effects": list(side_effects)}


def _param(name, type_name):
    return {"name": name, "type": [{"name": type_name}] if type_name else []}


def _set(name, n):
    return {"name": name, "members": [{"value": f"v{i}"} for i in range(n)]}


def _record(name, fields):
    return {"name": name, "record": [_param(fname, ftype) for fname, ftype in fields], "alias": []}


def _se(direction):
    return {"direction": direction, "target": "db"}


def _probe_exports():
    """The public surface is exactly these five names, in this order."""
    return (
        []
        if honest_estimate.__all__ == ["cfp", "depth", "elementary_processes", "size", "vfp"]
        else [f"__all__ drifted: {honest_estimate.__all__}"]
    )


def _probe_size_success():
    """size reads a .hd module and reports CFP, VFP, bits, and open flags, wrapped in ok()."""
    bad = []
    expected_a = {
        "ok": {
            "cosmic_cfp": 4,
            "vfp": {"total": 2, "ifpug_countable": 0, "beyond_ifpug_internal": 2, "internal_share_ratio": 1.0, "under_declared": False},
            "bits_of_case_distinction": 3.0,
            "open_vocab_flags": [],
            "cfp_certified": False,
        }
    }
    if size(_HD_A) != expected_a:
        bad.append(f"size fixture A: {size(_HD_A)}")
    expected_b = {
        "ok": {
            "cosmic_cfp": 2,
            "vfp": {"total": 1, "ifpug_countable": 0, "beyond_ifpug_internal": 1, "internal_share_ratio": 1.0, "under_declared": False},
            "bits_of_case_distinction": 1.0,
            "open_vocab_flags": [{"process": "act", "param": "note", "type": "str"}],
            "cfp_certified": False,
        }
    }
    if size(_HD_B) != expected_b:
        bad.append(f"size fixture B: {size(_HD_B)}")
    return bad


def _probe_size_faults():
    """A malformed .hd returns the read fault; a module-less .hd returns a no_module fault."""
    bad = []
    if "err" not in size("module m\n  fn broken : ("):
        bad.append("size on a malformed .hd should be an err Result")
    empty = size("# a comment, no module\n")
    if empty != {"err": {"code": "no_module", "message": "the .hd declares no module", "category": "client", "detail": {}}}:
        bad.append(f"size on a module-less .hd should fault no_module exactly: {empty}")
    return bad


def _probe_size_first_module():
    """When a source declares more than one module, size measures the first."""
    bad = []
    two = (
        'module first\n  layer tooling\n  set S = { "a", "b" }\n  boundary_in fn one : (x: S) -> str\n'
        "module second\n  layer tooling\n  boundary_in fn a : (p: str) -> str\n  boundary_in fn b : (q: str) -> str"
    )
    if size(two).get("ok", {}).get("vfp", {}).get("total") != 1:
        bad.append(f"size must measure the first declared module, not the last: {size(two)}")
    return bad


def _probe_elementary_processes():
    """The boundary role is the authority; the invoke-graph is only a fallback when no role exists."""
    bad = []
    # Roles populated: the processes are exactly the role-bearing functions, even one invoked by a
    # sibling. A pure fn (helper) that carries no role does not count while any role is present.
    roled = _module(functions=[
        _fn("edge", role="boundary_in", invokes=["helper"]),
        _fn("helper", role="fn"),
    ])
    if elementary_processes(roled) != ["edge"]:
        bad.append(f"role authority: {elementary_processes(roled)}")
    # For each role, a role-bearing function counts even when a sibling invokes it.
    for role in ("boundary_in", "boundary_out", "orchestrator"):
        m = _module(functions=[_fn("caller", role="fn", invokes=["contract"]), _fn("contract", role=role)])
        # caller has no role and IS a process only via... it carries no role, and a role exists, so
        # authority mode applies: only role-bearers count -> just contract.
        if elementary_processes(m) != ["contract"]:
            bad.append(f"a {role} contract must count under role authority: {elementary_processes(m)}")
    # No role at all -> fallback: a pure fn no sibling invokes is a contract; an invoked one is a helper.
    fallback = _module(functions=[_fn("root", invokes=["helper"]), _fn("helper")])
    if elementary_processes(fallback) != ["root"]:
        bad.append(f"fallback rule: {elementary_processes(fallback)}")
    return bad


def _probe_under_declared():
    """under_declared is true only when a module has functions but no boundary/orchestrator role."""
    bad = []
    if _under_declared(_module(functions=[_fn("x", role="boundary_in")])):
        bad.append("a module with a boundary role is not under-declared")
    if not _under_declared(_module(functions=[_fn("x", role="fn")])):
        bad.append("a module with functions but no role is under-declared")
    if _under_declared(_module()):
        bad.append("a module with no functions is not under-declared")
    return bad


def _probe_invoked_within():
    """Every name some sibling invokes."""
    bad = []
    got = _invoked_within(_module(functions=[_fn("a", invokes=["b", "c"]), _fn("b", invokes=["c"])]))
    if got != {"b", "c"}:
        bad.append(f"_invoked_within: {got}")
    return bad


def _probe_routed_targets():
    """The union of every route target and every entry target."""
    bad = []
    got = _routed_targets(_module(routes=[{"target": "r"}], entries=[{"target": "e"}]))
    if got != {"r", "e"}:
        bad.append(f"_routed_targets: {got}")
    return bad


def _probe_vfp():
    """The IFPUG split marks a routed process countable; a module with no process has a zero ratio."""
    bad = []
    routed = _module(functions=[_fn("h", role="boundary_in")], routes=[{"target": "h"}])
    if vfp(routed) != {"total": 1, "ifpug_countable": 1, "beyond_ifpug_internal": 0, "internal_share_ratio": 0.0, "under_declared": False}:
        bad.append(f"vfp routed split: {vfp(routed)}")
    if vfp(_module()) != {"total": 0, "ifpug_countable": 0, "beyond_ifpug_internal": 0, "internal_share_ratio": 0.0, "under_declared": False}:
        bad.append(f"vfp zero-process ratio: {vfp(_module())}")
    return bad


def _probe_process_movements():
    """Entry/eXit from the role, Read/Write per side effect, floored at two. Each role and effect value
    is made observable above the floor so a wrong constant changes the count; case 'f' pins the floor."""
    bad = []
    cases = [
        (_fn("a", role="boundary_in", side_effects=[_se("reads"), _se("reads")]), 3),  # role 1 + 2 reads
        (_fn("b", role="boundary_out", side_effects=[_se("reads"), _se("reads")]), 3),  # role 1 + 2 reads
        (_fn("c", role="orchestrator", side_effects=[_se("reads"), _se("reads"), _se("reads")]), 3),  # role 0 + 3
        (_fn("d", role="fn", side_effects=[_se("writes"), _se("writes"), _se("writes")]), 3),  # role 0 + 3 writes
        (_fn("e", role="boundary_in", side_effects=[_se("reads_writes")]), 3),  # role 1 + 2
        (_fn("f", role="boundary_in"), 2),  # role 1, floored to 2 (pins the floor both ways)
    ]
    for fn, want in cases:
        got = _process_movements(fn)
        if got != want:
            bad.append(f"_process_movements {fn['role']}/{[s['direction'] for s in fn['side_effects']]} -> {got}, want {want}")
    return bad


def _probe_cfp():
    """CFP is the sum of movements over the elementary processes only."""
    bad = []
    module = _module(functions=[
        _fn("proc", role="boundary_in", side_effects=[{"direction": "reads", "target": "db"}]),
        _fn("helper", role="fn"),
    ])
    # proc is the only process (role authority); helper carries no role -> excluded. proc = 1 + 1 = 2.
    if cfp(module) != 2:
        bad.append(f"cfp should sum only the processes' movements: {cfp(module)}")
    return bad


def _probe_cardinalities():
    """Set member counts, vocabulary sums over referenced sets, and composed-type field lists."""
    bad = []
    module = _module(
        sets=[_set("S", 2), _set("T", 3)],
        vocabularies=[{"name": "V", "sets": ["S", "T"]}, {"name": "W", "sets": ["S", "MISSING"]}],
        types=[_record("R", [("a", "S")]), {"name": "Alias", "record": [], "alias": [{"name": "S"}]}],
    )
    sets, vocabs, records = _cardinalities(module)
    if sets != {"S": 2, "T": 3}:
        bad.append(f"_cardinalities sets: {sets}")
    # V = S(2) + T(3) = 5; W = S(2) + MISSING(0, the default for an undeclared set) = 2.
    if vocabs != {"V": 5, "W": 2}:
        bad.append(f"_cardinalities vocab (sum of referenced sets, missing set counts zero): {vocabs}")
    if list(records) != ["R"]:
        bad.append(f"_cardinalities records (composed only, aliases excluded): {list(records)}")
    return bad


def _probe_head_atom():
    """The head atom name, or '' when the type is empty."""
    bad = []
    if _head_atom([{"name": "Head"}, {"name": "Tail"}]) != "Head":
        bad.append("_head_atom should read the head of a union type")
    if _head_atom([]) != "":
        bad.append("_head_atom on an empty type should be ''")
    return bad


def _probe_bits_of():
    """log-2 of a set or vocabulary; the sum over a composed type's fields; open otherwise; cycle-safe."""
    bad = []
    sets = {"S": 2, "T": 4}
    vocabs = {"V": 8}
    records = {"R": [_param("a", "S"), _param("b", "T"), _param("c", "str")], "Node": [_param("child", "Node")]}
    # set and vocabulary
    if _bits_of("S", sets, vocabs, records, frozenset(), "p", "x", []) != 1.0:
        bad.append("_bits_of over a 2-member set should be 1 bit")
    if _bits_of("V", sets, vocabs, records, frozenset(), "p", "x", []) != 3.0:
        bad.append("_bits_of over an 8-state vocabulary should be 3 bits")
    # composed type: 1 (S) + 2 (T) + 0 (open str) = 3, with the str field flagged.
    flags = []
    if _bits_of("R", sets, vocabs, records, frozenset(), "p", "arg", flags) != 3.0:
        bad.append("_bits_of should sum a composed type's field bits")
    if flags != [{"process": "p", "param": "arg.c", "type": "str"}]:
        bad.append(f"_bits_of should flag an open composed-type field with its path: {flags}")
    # a single-member set or single-state vocabulary is 0 bits (no distinction) but NOT open —
    # this pins the `> 0` cardinality guard, which a `> 1` mutant would send to the open branch.
    one_set = []
    if _bits_of("ONE", {"ONE": 1}, {}, {}, frozenset(), "p", "x", one_set) != 0.0 or one_set:
        bad.append(f"_bits_of over a 1-member set is 0 bits and not open: {one_set}")
    one_vocab = []
    if _bits_of("UNI", {}, {"UNI": 1}, {}, frozenset(), "p", "x", one_vocab) != 0.0 or one_vocab:
        bad.append(f"_bits_of over a 1-state vocabulary is 0 bits and not open: {one_vocab}")
    # open scalar and non-power-of-2 real logarithm.
    open_flags = []
    if _bits_of("str", sets, vocabs, records, frozenset(), "p", "y", open_flags) != 0.0 or open_flags != [{"process": "p", "param": "y", "type": "str"}]:
        bad.append(f"_bits_of on an open type should be 0 and flagged: {open_flags}")
    if not math.isclose(_bits_of("TRI", {"TRI": 3}, {}, {}, frozenset(), "p", "z", []), math.log2(3)):
        bad.append("_bits_of over a 3-member set should be log2(3)")
    # cycle guard: a self-referential composed type resolves to open once, never infinitely.
    cyc = []
    _bits_of("Node", sets, vocabs, records, frozenset(), "p", "n", cyc)
    if cyc != [{"process": "p", "param": "n.child", "type": "Node"}]:
        bad.append(f"_bits_of must break a composed-type cycle and flag it: {cyc}")
    return bad


def _probe_depth():
    """Only a process's input parameters contribute; a helper's parameters are skipped."""
    bad = []
    module = _module(
        functions=[
            _fn("proc", role="boundary_in", params=[_param("m", "S")]),
            _fn("helper", role="fn", params=[_param("z", "S")]),
        ],
        sets=[_set("S", 2)],
    )
    # proc is the only process; helper carries no role -> its param is skipped.
    if depth(module) != {"bits": 1.0, "open_flags": []}:
        bad.append(f"depth should skip a non-process function's params: {depth(module)}")
    return bad


_PROBES = (
    _probe_exports,
    _probe_size_success,
    _probe_size_faults,
    _probe_size_first_module,
    _probe_elementary_processes,
    _probe_under_declared,
    _probe_invoked_within,
    _probe_routed_targets,
    _probe_vfp,
    _probe_process_movements,
    _probe_cfp,
    _probe_cardinalities,
    _probe_head_atom,
    _probe_bits_of,
    _probe_depth,
)


def run():
    failures = [f for probe in _PROBES for f in probe()]
    for f in failures:
        print(f"FAIL honest-estimate law: {f}")
    print(f"honest-estimate laws: {len(_PROBES)} probes, {len(failures)} failed")
    return 0 if not failures else 1
