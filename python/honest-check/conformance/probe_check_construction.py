# scenario: check_construction
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction
"""Honest probe for honest-check's check_construction (feature Scenario: check_construction).

check_construction is the construction-time rule sub-core: it runs HC001, HC003, HC006,
HC007, HC011 and the state-machine rules over the one CheckContext build_context assembled,
and returns the construction-time findings as data. The feature scenario names HC007 (an
empty chain) as one of its rules, and the startup_check note pins the concrete trigger: a
framework chain() call constructed with no links fires HC007 at error severity. So the
violation case builds a real CheckContext over source holding an empty chain() and demands a
Diagnostic whose rule_id is HC007; the clean case holds no construction call and demands the
empty list. A trivial `return []` stub passes the clean case and fails the HC007 case.

The input is a real parse: build_context parses the crafted source under honest-parse's Python
grammar and assembles the CheckContext check_construction reads. No fabricated nodes.
"""

# Each case: crafted Python source (bytes), and the construction-rule verdict it must produce.
# "must_contain" names a rule_id that must appear; "must_be_empty" demands no finding at all.
_CASES = [
    {
        "desc": "an empty chain() fires HC007",
        "source": b"from honest_type import chain\nreport = chain()\n",
        "must_contain": "HC007",
        "must_be_empty": False,
    },
    {
        "desc": "source with no construction call is clean",
        "source": b"x = 1\n",
        "must_contain": None,
        "must_be_empty": True,
    },
]


def probe_check_construction():
    """check_construction fires HC007 on an empty chain() and returns nothing on clean source."""
    try:
        from honest_check import build_context, check_construction
    except ImportError as exc:
        return [f"cannot import check_construction: {exc}"]

    bad = []
    for case in _CASES:
        ctx = build_context(source=case["source"], path="probe.py", rule_config={})
        got = check_construction(ctx=ctx)
        ids = [d["rule_id"] for d in got]
        if case["must_be_empty"]:
            if got != []:
                bad.append(
                    f"check_construction({case['desc']}) -> {ids}, expected no findings"
                )
        elif case["must_contain"] not in ids:
            bad.append(
                f"check_construction({case['desc']}) -> {ids}, "
                f"expected a {case['must_contain']} finding"
            )
    for reference in ("os.environ", "sys.argv", "sys.version", "sys.path", "__file__", "__name__"):
        for decorator, expected in (("@link()", [("warning", "probe.py", "4")]), ("@link(boundary=True)", [])):
            source = f"from honest_type import link\nimport os, sys\n{decorator}\ndef observe():\n    return {reference}\n"
            context = build_context(source=source.encode(), path="probe.py", rule_config={})
            findings = check_construction(ctx=context)
            warnings = [
                (finding["severity"], *finding["source_location"].rsplit(":", 2)[:2])
                for finding in findings if finding["rule_id"] == "HC008"
            ]
            if warnings != expected:
                bad.append(
                    f"check_construction({decorator} reads {reference}) gave HC008 {warnings!r}, "
                    f"expected {expected!r}"
                )
    return bad
