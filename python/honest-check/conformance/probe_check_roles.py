# scenario: check_roles
# inherits: hd=python/honest-check/honest-check.hd::check_roles -> feature=specs/features/honest-check.feature::check_roles
"""Honest probe for honest-check's check_roles (feature Scenario: check_roles).

check_roles runs the whole-program orphan rule HC-R001 over a module's code files and its
declaration. A top-level function is roled when it carries a role decorator or the declaration
names it; the rule builds the whole-program call graph, computes the functions reachable from
the roled set, and emits one HC-R001 error for each top-level function that is neither roled
nor reachable. When there are no roled functions at all (no role decorator and declaration is
NOTHING) it emits nothing rather than flagging every function.

Five cases, all with declaration NOTHING (None):
- an orphan case: `run` is roled by @orchestrator and calls `worker` (reachable), while
  `orphan` is neither roled nor reachable -> exactly one HC-R001;
- a clean case: `run` is roled and `worker` is reachable, nothing orphaned -> no finding;
- the explicit stand-down case named by the scenario: no decorator anywhere and NOTHING ->
  the roled set is empty, so the rule stands down and emits nothing;
- a dispatch-table case: a roled `run` references the module-scope dict `handlers` by name, and
  `picked` is reached only as a value of that dict (never called syntactically) -> no finding,
  because reachability follows a referenced dispatch table (§HC-R001, P16);
- a stranded-dict case: `stranded` sits in a dict `unused` that nothing reachable references, so
  the dict never becomes reachable and its value stays an orphan -> exactly one HC-R001.

A `return []` stub passes the empty cases and fails the two orphan cases. The package is real:
pair_source joins each path to its bytes into a SourceFile. No fabricated nodes.
"""

# An @orchestrator-roled run calls worker (reachable); orphan is neither roled nor reachable.
_ORPHAN_SOURCE = (
    b"@orchestrator\n"
    b"def run():\n"
    b"    worker()\n"
    b"\n"
    b"def worker():\n"
    b"    pass\n"
    b"\n"
    b"def orphan():\n"
    b"    pass\n"
)

# An @orchestrator-roled run calls worker; every function is roled or reachable.
_CLEAN_SOURCE = (
    b"@orchestrator\n"
    b"def run():\n"
    b"    worker()\n"
    b"\n"
    b"def worker():\n"
    b"    pass\n"
)

# No role decorator anywhere; with declaration NOTHING the roled set is empty, so the rule stands down.
_NO_ROLES_SOURCE = (
    b"def a():\n"
    b"    pass\n"
    b"\n"
    b"def b():\n"
    b"    pass\n"
)

# A roled `run` references the module-scope dispatch dict `handlers` by name; `picked` is a value of
# that dict and is reached only through the table, never called syntactically. It must NOT be an orphan.
_DISPATCH_REACHED_SOURCE = (
    b"@orchestrator\n"
    b"def run(kind):\n"
    b"    return handlers[kind]\n"
    b"\n"
    b"def picked():\n"
    b"    pass\n"
    b"\n"
    b"handlers = {'only': picked}\n"
)

# `stranded` sits in the dict `unused`, which nothing reachable references; the roled `run` calls only
# `worker`. The dict never becomes reachable, so its value stays an orphan: exactly one HC-R001.
_DISPATCH_UNREFERENCED_SOURCE = (
    b"@orchestrator\n"
    b"def run():\n"
    b"    worker()\n"
    b"\n"
    b"def worker():\n"
    b"    pass\n"
    b"\n"
    b"def stranded():\n"
    b"    pass\n"
    b"\n"
    b"unused = {'x': stranded}\n"
)

# A roled, fully-reachable module carrying two module-scope assignments that are not dispatch tables:
# `config = 42` is a non-dict binding, and `empty = {'a': 1}` is a dict whose values name no function.
# Neither contributes a dispatch node; nothing is orphaned -> no finding.
_NON_TABLE_ASSIGNMENTS_SOURCE = (
    b"@orchestrator\n"
    b"def run():\n"
    b"    worker()\n"
    b"\n"
    b"def worker():\n"
    b"    pass\n"
    b"\n"
    b"config = 42\n"
    b"empty = {'a': 1}\n"
)

# Each case: the package's code (bytes), and the HC-R001 count it must produce. declaration is NOTHING.
_CASES = [
    {"desc": "an unreachable, unroled function is one orphan", "source": _ORPHAN_SOURCE, "expect_hc_r001": 1},
    {
        "desc": "a module expression combining a dict with another value does not bind a dispatch table",
        "source": (
            b"@orchestrator\ndef root(kind): return handlers[kind]\n"
            b"def stranded(): pass\n"
            b"handlers = {}\n"
            b"handlers | {'x': stranded}\n"
        ),
        "expect_hc_r001": 1,
    },
    {
        "desc": "a computed dictionary comprehension does not declare a literal dispatch table",
        "source": (
            b"@orchestrator\ndef root(kind): return handlers[kind]\n"
            b"def stranded(): pass\n"
            b"handlers = {name: stranded for name in ()}\n"
        ),
        "expect_hc_r001": 1,
    },
    *[
        {
            "desc": f"@{role} starts reachability while orphan stays unroled",
            "source": b"@" + role.encode() + b"\ndef root(): pass\ndef orphan(): pass\n",
            "expect_hc_r001": 1,
        }
        for role in ("link", "recognizer", "boundary", "helper")
    ],
    {"desc": "every function is roled or reachable", "source": _CLEAN_SOURCE, "expect_hc_r001": 0},
    {"desc": "no roles adopted at all stands the rule down", "source": _NO_ROLES_SOURCE, "expect_hc_r001": 0},
    {"desc": "a handler reached only through a referenced dispatch dict is not an orphan", "source": _DISPATCH_REACHED_SOURCE, "expect_hc_r001": 0},
    {"desc": "a function in a dict nothing references stays an orphan", "source": _DISPATCH_UNREFERENCED_SOURCE, "expect_hc_r001": 1},
    {
        "desc": "a referenced dispatch table does not make a same-named function reachable",
        "source": (
            b"@orchestrator\ndef run(kind): return handlers[kind]\n"
            b"def handlers(): pass\n"
            b"def picked(): pass\n"
            b"handlers = {'only': picked}\n"
        ),
        "expect_hc_r001": 1,
    },
    {"desc": "non-dict and non-function-valued module assignments contribute no dispatch node", "source": _NON_TABLE_ASSIGNMENTS_SOURCE, "expect_hc_r001": 0},
]


def probe_check_roles():
    """check_roles emits one HC-R001 per orphan and nothing when roles are adopted everywhere or not at all."""
    try:
        from honest_check import check_roles, pair_source
    except ImportError as exc:
        return [f"cannot import check_roles: {exc}"]

    bad = []
    for case in _CASES:
        sources = [pair_source(path="mod.py", text=case["source"])]
        got = check_roles(sources=sources, declaration=None)
        for finding in got:
            if finding["rule_id"] != "HC-R001" or finding["severity"] != "error":
                bad.append(f"unexpected orphan finding: {finding!r}")
            if not finding["message"].strip():
                bad.append(f"orphan finding has no explanation: {finding!r}")
        hc_r001 = [d["rule_id"] for d in got if d["rule_id"] == "HC-R001"]
        if len(hc_r001) != case["expect_hc_r001"]:
            bad.append(
                f"check_roles({case['desc']}) -> {len(hc_r001)} HC-R001 "
                f"(all rule_ids {[d['rule_id'] for d in got]}), "
                f"expected {case['expect_hc_r001']}"
            )
    from honest_design import read_hd

    declared = read_hd(
        'module demo\n  layer correctness\n  fn root : () -> int note "receives calls by declaration"\n'
    )["ok"]["modules"][0]
    declared_sources = [
        pair_source(path="mod.py", text=b"def root(): return 1\ndef orphan(): return 2\n")
    ]
    findings = check_roles(sources=declared_sources, declaration=declared)
    declared_ids = [(finding["rule_id"], finding["severity"], "orphan" in finding["message"])
                    for finding in findings]
    if declared_ids != [("HC-R001", "error", True)]:
        bad.append(f"the declaration makes only root reachable; expected orphan, got {findings!r}")
    return bad
