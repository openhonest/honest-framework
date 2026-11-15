"""Honest probe for honest-check's resolve_rule_config (feature Scenario: resolve_rule_config).

resolve_rule_config is pure: it builds the [rules] RuleConfig from a parsed
honest-check.toml [rules] table, returning {"HC-OR003": {"min_run": N}} when the
project set min_run and the empty map otherwise. It fills in no documented default
(build_context merges min_run = 3 later). The cases pin both non-trivial outputs
(two different min_run values, so the result is read from the data and not
hardcoded) and the empty-map case for every shape where the project set no
min_run. A `return {}` stub fails the populated cases; a `return data` identity
stub fails the "other rule id" and "HC-OR003 without min_run" cases.
"""

# Each case: the parsed [rules] table, and the RuleConfig resolve_rule_config must return.
_CASES = [
    # The project set min_run: the one configurable rule's setting is carried through.
    {"given": {"HC-OR003": {"min_run": 3}}, "expect": {"HC-OR003": {"min_run": 3}}},
    # A different value proves the result is read from the data, not hardcoded.
    {"given": {"HC-OR003": {"min_run": 9}}, "expect": {"HC-OR003": {"min_run": 9}}},
    # The project set nothing: the empty map.
    {"given": {}, "expect": {}},
    # Another rule id but no HC-OR003 min_run: the empty map (otherwise).
    {"given": {"HC-P008": {"max_lines": 50}}, "expect": {}},
    # HC-OR003 present but min_run absent: the project did not set min_run -> empty map.
    {"given": {"HC-OR003": {}}, "expect": {}},
]


def probe_resolve_rule_config():
    """resolve_rule_config returns {'HC-OR003': {'min_run': N}} when set, else {}."""
    try:
        from honest_check import resolve_rule_config
    except ImportError as exc:
        return [f"cannot import resolve_rule_config: {exc}"]

    bad = []
    for case in _CASES:
        got = resolve_rule_config(data=case["given"])
        if got != case["expect"]:
            bad.append(
                f"resolve_rule_config({case['given']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
