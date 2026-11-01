from honest_check import check_source

# check_source(source, path, rule_config) -> list[Diagnostic]
# A violating source comes back with a Diagnostic whose rule_id is the
# catalogue id of the rule that fired; a clean source comes back empty.
# The exact per-rule source-to-diagnostic mapping is the conformance
# suite's job (section 9.2), so this probe pins only one rule: the bare
# class declaration HC-P003, plus the explicit clean case.

_RULE_CONFIG = {
    "HC-OR003": {"min_run": 3},
    "HC-P008": {"max_lines": 10},
    "HC-P012": {"max_mocks": 2},
}

_CLASS_SOURCE = "class Foo:\n    pass\n"
_CLEAN_SOURCE = "x = 1\n"

_CASES = [
    {
        "given": {
            "source": _CLASS_SOURCE,
            "path": "app.py",
            "rule_config": _RULE_CONFIG,
        },
        # a bare class fires HC-P003; at least one diagnostic carries that id
        "expect_rule": "HC-P003",
    },
    {
        "given": {
            "source": _CLEAN_SOURCE,
            "path": "app.py",
            "rule_config": _RULE_CONFIG,
        },
        # no violation: the returned list is empty
        "expect_rule": None,
    },
]


def probe_check_source():
    """A violating source returns a Diagnostic carrying the fired rule's id; a clean source returns []."""
    bad = []
    for case in _CASES:
        got = check_source(**case["given"])
        rule = case["expect_rule"]
        if rule is None:
            if got != []:
                bad.append(
                    f"check_source({case['given']}) -> {got}, expected [] (clean source)"
                )
            continue
        fired = [d["rule_id"] for d in got]
        if rule not in fired:
            bad.append(
                f"check_source({case['given']}) -> rule_ids {fired}, expected {rule} among them"
            )
    return bad
