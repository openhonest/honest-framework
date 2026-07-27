"""honest-estimate conformance: the generative proof.

Probes every branch of the two emitters: the widened §7.1 process rule (a boundary/orchestrator role,
or a pure fn no sibling invokes; an invoked pure fn is an interior helper and does not count), the
IFPUG breadth split and its zero-process ratio, the closed-vocabulary depth in real bits, the §7.3
open-parameter flagging, and the size boundary's success and two fault paths. Each probe returns a
list of failures; run() aggregates.
"""

import math

import honest_estimate
from honest_estimate import breadth, depth, elementary_processes, size
from honest_estimate.estimate import _param_type_name, _routed_targets


def _probe_exports():
    """The public surface is exactly these four names, in this order."""
    return (
        []
        if honest_estimate.__all__ == ["breadth", "depth", "elementary_processes", "size"]
        else [f"__all__ drifted: {honest_estimate.__all__}"]
    )

_HD_A = (
    'module m\n  layer tooling\n  set PAIR = { "a", "b" }\n  set QUAD = { "w", "x", "y", "z" }\n'
    "  boundary_in fn recognise : (raw: PAIR) -> str\n  fn transform : (v: QUAD) -> str"
)
_HD_B = (
    'module m\n  layer tooling\n  set MODE = { "on", "off" }\n'
    "  boundary_in fn act : (mode: MODE, note: str) -> str"
)


def _module(functions=(), sets=(), routes=(), entries=()):
    return {"functions": list(functions), "sets": list(sets), "routes": list(routes), "entries": list(entries)}


def _fn(name, role="fn", invokes=(), params=()):
    return {"name": name, "role": role, "invokes": list(invokes), "params": list(params)}


def _param(name, type_name):
    return {"name": name, "type": [{"name": type_name}] if type_name else []}


def _set(name, n):
    return {"name": name, "members": [{"value": f"v{i}"} for i in range(n)]}


def _probe_size_success():
    """size reads a .hd module and reports its breadth, bits, and open flags, wrapped in ok()."""
    bad = []
    a = size(_HD_A)
    expected_a = {
        "ok": {
            "processes": {"total": 2, "ifpug_countable": 0, "beyond_ifpug_internal": 2, "internal_share_ratio": 1.0},
            "bits_of_case_distinction": 3.0,
            "open_vocabulary_flags": [],
        }
    }
    if a != expected_a:
        bad.append(f"size fixture A: {a}")
    b = size(_HD_B)
    expected_b = {
        "ok": {
            "processes": {"total": 1, "ifpug_countable": 0, "beyond_ifpug_internal": 1, "internal_share_ratio": 1.0},
            "bits_of_case_distinction": 1.0,
            "open_vocabulary_flags": [{"process": "act", "param": "note", "type": "str"}],
        }
    }
    if b != expected_b:
        bad.append(f"size fixture B: {b}")
    return bad


def _probe_size_faults():
    """A malformed .hd returns the read fault; a module-less .hd returns a no_module fault."""
    bad = []
    malformed = size("module m\n  fn broken : (")
    if "err" not in malformed:
        bad.append(f"size on a malformed .hd should be an err Result: {malformed}")
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
    got = size(two)
    if got.get("ok", {}).get("processes", {}).get("total") != 1:
        bad.append(f"size must measure the first declared module, not the last: {got}")
    return bad


def _probe_roles_count_when_invoked():
    """Each boundary/orchestrator role makes a function a process even when a sibling invokes it —
    the role clause, not the not-invoked clause, is what counts it."""
    bad = []
    for role in ("boundary_in", "boundary_out", "orchestrator"):
        module = _module(functions=[_fn("caller", role="fn", invokes=["contract"]), _fn("contract", role=role)])
        if "contract" not in elementary_processes(module):
            bad.append(f"a {role} contract invoked by a sibling must still count as a process")
    return bad


def _probe_elementary_processes():
    """A boundary role counts; a pure fn no sibling invokes counts; an invoked pure fn is a helper."""
    bad = []
    module = _module(functions=[
        _fn("edge", role="boundary_in", invokes=["helper"]),
        _fn("root", role="fn", invokes=["helper"]),
        _fn("helper", role="fn"),
    ])
    got = elementary_processes(module)
    if got != ["edge", "root"]:
        bad.append(f"elementary_processes widened rule: {got}")
    if "helper" in got:
        bad.append("an invoked pure fn must not count as a process")
    return bad


def _probe_breadth():
    """The IFPUG split marks a routed process countable; a module with no process has a zero ratio."""
    bad = []
    routed = _module(functions=[_fn("h", role="boundary_in")], routes=[{"target": "h"}])
    got = breadth(routed)
    if got != {"total": 1, "ifpug_countable": 1, "beyond_ifpug_internal": 0, "internal_share_ratio": 0.0}:
        bad.append(f"breadth routed split: {got}")
    empty = breadth(_module())
    if empty != {"total": 0, "ifpug_countable": 0, "beyond_ifpug_internal": 0, "internal_share_ratio": 0.0}:
        bad.append(f"breadth zero-process ratio: {empty}")
    return bad


def _probe_param_type_name():
    """The head type atom, or '' when the parameter's type is empty."""
    bad = []
    if _param_type_name({"name": "x", "type": [{"name": "T"}]}) != "T":
        bad.append("_param_type_name should read the head atom")
    if _param_type_name({"name": "x", "type": [{"name": "Head"}, {"name": "Tail"}]}) != "Head":
        bad.append("_param_type_name should read the head of a union type, not the last atom")
    if _param_type_name({"name": "x", "type": []}) != "":
        bad.append("_param_type_name on an empty type should be ''")
    return bad


def _probe_routed_targets():
    """The union of every route target and every entry target."""
    bad = []
    got = _routed_targets(_module(routes=[{"target": "r"}], entries=[{"target": "e"}]))
    if got != {"r", "e"}:
        bad.append(f"_routed_targets should union routes and entries: {got}")
    return bad


def _probe_depth():
    """Only a process's parameters contribute; a set of cardinality N contributes log-2 N."""
    bad = []
    module = _module(
        functions=[
            _fn("proc", role="boundary_in", invokes=["help"], params=[_param("m", "S")]),
            _fn("help", role="fn", params=[_param("z", "S")]),
        ],
        sets=[_set("S", 2)],
    )
    if depth(module) != {"bits": 1.0, "open_flags": []}:
        bad.append(f"depth should skip an invoked helper's params: {depth(module)}")
    three = _module(functions=[_fn("p", role="boundary_in", params=[_param("k", "TRI")])], sets=[_set("TRI", 3)])
    bits = depth(three)["bits"]
    if not math.isclose(bits, math.log2(3)):
        bad.append(f"depth over a 3-member set should be log2(3): {bits}")
    return bad


_PROBES = (
    _probe_exports,
    _probe_size_success,
    _probe_size_faults,
    _probe_size_first_module,
    _probe_elementary_processes,
    _probe_roles_count_when_invoked,
    _probe_breadth,
    _probe_param_type_name,
    _probe_routed_targets,
    _probe_depth,
)


def run():
    failures = [f for probe in _PROBES for f in probe()]
    for f in failures:
        print(f"FAIL honest-estimate law: {f}")
    print(f"honest-estimate laws: {len(_PROBES)} probes, {len(failures)} failed")
    return 0 if not failures else 1
