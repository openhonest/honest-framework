"""Honest probe for honest-check's check_roles (feature Scenario: check_roles).

check_roles runs the whole-program orphan rule HC-R001 over a module's code files and its
declaration. A top-level function is roled when it carries a role decorator or the declaration
names it; the rule builds the whole-program call graph, computes the functions reachable from
the roled set, and emits one HC-R001 error for each top-level function that is neither roled
nor reachable. When there are no roled functions at all (no role decorator and declaration is
NOTHING) it emits nothing rather than flagging every function.

Three cases, all with declaration NOTHING (None):
- an orphan case: `run` is roled by @orchestrator and calls `worker` (reachable), while
  `orphan` is neither roled nor reachable -> exactly one HC-R001;
- a clean case: `run` is roled and `worker` is reachable, nothing orphaned -> no finding;
- the explicit stand-down case named by the scenario: no decorator anywhere and NOTHING ->
  the roled set is empty, so the rule stands down and emits nothing.

A `return []` stub passes the two empty cases and fails the orphan case. The package is real:
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

# Each case: the package's code (bytes), and the HC-R001 count it must produce. declaration is NOTHING.
_CASES = [
    {"desc": "an unreachable, unroled function is one orphan", "source": _ORPHAN_SOURCE, "expect_hc_r001": 1},
    {"desc": "every function is roled or reachable", "source": _CLEAN_SOURCE, "expect_hc_r001": 0},
    {"desc": "no roles adopted at all stands the rule down", "source": _NO_ROLES_SOURCE, "expect_hc_r001": 0},
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
        hc_r001 = [d["rule_id"] for d in got if d["rule_id"] == "HC-R001"]
        if len(hc_r001) != case["expect_hc_r001"]:
            bad.append(
                f"check_roles({case['desc']}) -> {len(hc_r001)} HC-R001 "
                f"(all rule_ids {[d['rule_id'] for d in got]}), "
                f"expected {case['expect_hc_r001']}"
            )
    return bad
