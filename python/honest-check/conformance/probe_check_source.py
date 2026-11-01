"""check_source folds the rule catalogue over one source's declaration graph and
returns findings as data: a class declaration fires HC-P003, a clean source is [].

Pins the function contract, not the per-rule specifics (those are suite.json's job):
findings come back as a list of Diagnostic, a class source carries an HC-P003
finding, and a clean source returns the empty list. It never raises for a violation.
"""

# A class declaration carries an HC-P003 finding; a clean assignment is clean.
# want_rule None is the explicit clean (absence) case: the empty list, written out.
_CASES = [
    {
        "given": {"source": "class Report:\n    pass\n", "path": "a.py", "rule_config": {}},
        "want_rule": "HC-P003",
    },
    {
        "given": {"source": "x = 1\n", "path": "a.py", "rule_config": {}},
        "want_rule": None,
    },
]


def probe_check_source():
    try:
        from honest_check import check_source
    except ImportError as exc:
        return [f"cannot import check_source: {exc}"]

    bad = []
    for case in _CASES:
        got = check_source(**case["given"])
        if not isinstance(got, list):
            bad.append(f"check_source({case['given']}) -> {got!r}, expected a list")
            continue
        rule_ids = [d.get("rule_id") for d in got]
        if case["want_rule"] is None:
            if got != []:
                bad.append(
                    f"check_source({case['given']}) -> {got!r}, expected [] (clean source)"
                )
        elif case["want_rule"] not in rule_ids:
            bad.append(
                f"check_source({case['given']}) -> rule_ids {rule_ids}, "
                f"expected one to be {case['want_rule']!r}"
            )
    return bad
