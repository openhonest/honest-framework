"""check_roles folds the orphan-function rule HC-R001 over the whole package of
code files and returns the orphans as data. This probe is the test-of-record for
HC-R001: an orphan is a top-level function that no role reaches, and reachability
crosses files (a function roled in one file can reach a function defined in
another), so the rule cannot be pinned by the single-source conformance suite the
way check_source's per-file rules are.

Each case builds its own small `sources` list inline, pairs it with a declaration
(NOTHING as None, or a parsed .hd module), calls the real check_roles over it, and
checks the findings two ways: the set of (rule_id, severity) pairs over the whole
returned list equals the set the case fixes, and every expected finding points at
the offending function's file (its path appears in the diagnostic's
source_location), so a case does not depend on an exact column.

A stub returning [] passes the three clean/stand-down cases but fails the one firing
case, so the probe is not vacuous.

Spec authority: §HC-R001 (orphan functions, one error each at severity 'error',
section 8). When no function is roled at all, the role system is not in use and the
pass emits nothing.
"""

# Each case: a name, the package sources, the declaration .hd text (None for the
# NOTHING absence value), and the findings it fixes as (rule_id, severity,
# offending_path) triples. The clean, stand-down and declaration-role cases fix the
# empty list, written out, because the scenario names them explicitly.
_CASES = [
    # Orphan fires — one file carries a @boundary handler and a stray function the
    # call graph never reaches from a roled function.
    {
        "name": "orphan fires (stray unreached)",
        "sources": [
            {
                "path": "m.py",
                "text": "@boundary\ndef handler(m):\n    return m\n\n\ndef stray(m):\n    return m\n",
            },
        ],
        "hd": None,
        "want": [("HC-R001", "error", "m.py")],
    },
    # Reachable is clean — helper is called by the roled handler, so it is reached
    # from the roled set and is not an orphan.
    {
        "name": "reachable is clean (helper reached from boundary)",
        "sources": [
            {
                "path": "m.py",
                "text": "@boundary\ndef handler(m):\n    return helper(m)\n\n\ndef helper(m):\n    return m\n",
            },
        ],
        "hd": None,
        "want": [],
    },
    # No-roles stand-down — a file of only plain functions, no decorators and no
    # declaration, so the roled set is empty and the rule stands down entirely.
    {
        "name": "no-roles stand-down (role system not in use)",
        "sources": [
            {
                "path": "m.py",
                "text": "def one(m):\n    return m\n\n\ndef two(m):\n    return m\n",
            },
        ],
        "hd": None,
        "want": [],
    },
    # Declaration-sourced role — save wears no decorator but the .hd names it, so
    # save is roled by its declaration and is not an orphan.
    {
        "name": "declaration-sourced role (save declared, no decorator)",
        "sources": [
            {"path": "m.py", "text": "def save(m):\n    return m\n"},
        ],
        "hd": 'module m\n  boundary_in fn save : (x: str) -> str side_effect reads "filesystem"\n',
        "want": [],
    },
    # Cross-file reachability — the roled entry in file A calls work in file B, so
    # work is reached across files and is not an orphan. This proves the pass is
    # whole-program, not per-file: viewed per-file, work would look orphaned.
    {
        "name": "cross-file reachability (work reached from another file)",
        "sources": [
            {"path": "a.py", "text": "@boundary\ndef entry(m):\n    return work(m)\n"},
            {"path": "b.py", "text": "def work(m):\n    return m\n"},
        ],
        "hd": None,
        "want": [],
    },
]


def _pairs(findings):
    """The (rule_id, severity) set a run produced, as a sorted list for comparison."""
    return sorted((d.get("rule_id"), d.get("severity")) for d in findings)


def _want_pairs(want):
    """The (rule_id, severity) set a case fixes, as a sorted list."""
    return sorted((rule_id, severity) for rule_id, severity, _ in want)


def probe_check_roles():
    """check_roles reports every top-level function that is neither roled nor
    reachable across the whole package as an HC-R001 error Diagnostic that points
    at the offending function's file, reports nothing for a function reached from a
    roled function (in any file) or roled by the declaration, and stands the rule
    down with nothing when no function is roled at all."""
    try:
        from honest_check import check_roles
    except ImportError as exc:
        return [f"cannot import check_roles: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        declaration = None
        if case["hd"] is not None:
            parsed = read_hd(case["hd"])
            if "ok" not in parsed:
                bad.append(
                    f"{case['name']}: fixture .hd did not parse: {parsed.get('err')!r}"
                )
                continue
            declaration = parsed["ok"]["modules"][0]

        got = check_roles(case["sources"], declaration)
        if not isinstance(got, list):
            bad.append(f"{case['name']}: check_roles -> {got!r}, expected a list")
            continue

        got_pairs = _pairs(got)
        want_pairs = _want_pairs(case["want"])
        if got_pairs != want_pairs:
            bad.append(
                f"{case['name']}: (rule_id, severity) pairs {got_pairs}, "
                f"expected {want_pairs}"
            )

        for rule_id, severity, path in case["want"]:
            pointed = [
                d
                for d in got
                if d.get("rule_id") == rule_id
                and d.get("severity") == severity
                and path in str(d.get("source_location", ""))
            ]
            if not pointed:
                locations = [
                    (d.get("rule_id"), d.get("source_location")) for d in got
                ]
                bad.append(
                    f"{case['name']}: no {rule_id} {severity} finding points at "
                    f"{path!r}; findings were {locations}"
                )
    return bad
