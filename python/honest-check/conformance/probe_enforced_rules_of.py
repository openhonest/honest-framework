"""enforced_rules_of returns the cumulative rules a level enforces (section 9.4).

HC-P001 is enforced at Structural; HC-SYN holds at every level; HC001 is not
enforced at Structural but is at Typed; Declared enforces all 50 rules the levels
cover.
"""

# present True: the rule must be enforced at that level. present False: it must not.
_MEMBERSHIP = [
    {"level": "Structural", "rule": "HC-P001", "present": True},
    {"level": "Structural", "rule": "HC-SYN", "present": True},
    {"level": "Boundary", "rule": "HC-SYN", "present": True},
    {"level": "Typed", "rule": "HC-SYN", "present": True},
    {"level": "Declared", "rule": "HC-SYN", "present": True},
    {"level": "Structural", "rule": "HC001", "present": False},
    {"level": "Typed", "rule": "HC001", "present": True},
]

# The strictest level enforces every rule the levels cover.
_COUNTS = [
    {"level": "Declared", "count": 50},
]


def probe_enforced_rules_of():
    try:
        from honest_check import enforced_rules_of
    except ImportError as exc:
        return [f"cannot import enforced_rules_of: {exc}"]

    bad = []
    for case in _MEMBERSHIP:
        got = enforced_rules_of(case["level"])
        present = case["rule"] in got
        if present != case["present"]:
            bad.append(
                f"enforced_rules_of({case['level']!r}): {case['rule']!r} present={present}, "
                f"expected present={case['present']}"
            )
    for case in _COUNTS:
        got = enforced_rules_of(case["level"])
        if len(got) != case["count"]:
            bad.append(
                f"len(enforced_rules_of({case['level']!r})) -> {len(got)}, "
                f"expected {case['count']}"
            )
    return bad
