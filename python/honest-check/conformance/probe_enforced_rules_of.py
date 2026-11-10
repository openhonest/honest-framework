"""enforced_rules_of returns the cumulative rules a level enforces (section 9.4).

always_rules hold at every level; each level adds its own set on top of the levels
below it. HC-P001 is enforced at Structural; HC-SYN holds everywhere; HC001 is not
enforced at Structural but is at Typed. The four levels enforce 11, 20, 39 and 58
rules, so every rule name and the cumulative slice are pinned by one membership
case and one count case apiece.
"""

# present True: the rule must be enforced at that level. present False: it must not.
# One present-True entry per rule names the exact level that first enforces it, so an
# emptied rule name in any adoption set drops that rule out of the returned list and
# flips present to False.
_MEMBERSHIP = [
    # always_rules, enforced at every level (checked at the lowest).
    {"level": "Structural", "rule": "HC-SYN", "present": True},
    {"level": "Structural", "rule": "HC-SUP001", "present": True},
    {"level": "Structural", "rule": "HC-SUP002", "present": True},
    {"level": "Boundary", "rule": "HC-SYN", "present": True},
    {"level": "Typed", "rule": "HC-SYN", "present": True},
    {"level": "Declared", "rule": "HC-SYN", "present": True},
    # Structural set.
    {"level": "Structural", "rule": "HC-P001", "present": True},
    {"level": "Structural", "rule": "HC-P003", "present": True},
    {"level": "Structural", "rule": "HC-P007", "present": True},
    {"level": "Structural", "rule": "HC-P011", "present": True},
    {"level": "Structural", "rule": "HC-P016", "present": True},
    # Boundary set: not yet enforced at Structural, enforced at Boundary.
    {"level": "Structural", "rule": "HC-P002", "present": False},
    {"level": "Boundary", "rule": "HC-P002", "present": True},
    {"level": "Boundary", "rule": "HC-P004", "present": True},
    {"level": "Boundary", "rule": "HC-P005", "present": True},
    {"level": "Boundary", "rule": "HC-P006", "present": True},
    {"level": "Boundary", "rule": "HC-P010", "present": True},
    {"level": "Boundary", "rule": "HC-P013", "present": True},
    {"level": "Boundary", "rule": "HC-ST001", "present": True},
    {"level": "Boundary", "rule": "HC-A001", "present": True},
    {"level": "Boundary", "rule": "HC-A002", "present": True},
    # Typed set: not yet enforced at Structural, enforced at Typed.
    {"level": "Structural", "rule": "HC001", "present": False},
    {"level": "Typed", "rule": "HC001", "present": True},
    {"level": "Typed", "rule": "HC002", "present": True},
    {"level": "Typed", "rule": "HC003", "present": True},
    {"level": "Typed", "rule": "HC004", "present": True},
    {"level": "Typed", "rule": "HC005", "present": True},
    {"level": "Typed", "rule": "HC006", "present": True},
    {"level": "Typed", "rule": "HC007", "present": True},
    {"level": "Typed", "rule": "HC008", "present": True},
    {"level": "Typed", "rule": "HC009", "present": True},
    {"level": "Typed", "rule": "HC010", "present": True},
    {"level": "Typed", "rule": "HC011", "present": True},
    {"level": "Typed", "rule": "HC-SM01", "present": True},
    {"level": "Typed", "rule": "HC-SM02", "present": True},
    {"level": "Typed", "rule": "HC-SM03", "present": True},
    {"level": "Typed", "rule": "HC-SM04", "present": True},
    {"level": "Typed", "rule": "HC-SM05", "present": True},
    {"level": "Typed", "rule": "HC-P014", "present": True},
    {"level": "Typed", "rule": "HC-P017", "present": True},
    # Declared set: enforced only at the strictest level.
    {"level": "Declared", "rule": "HC-R001", "present": True},
    {"level": "Declared", "rule": "HC-R002", "present": True},
    {"level": "Declared", "rule": "HC-R003", "present": True},
    {"level": "Declared", "rule": "HC-R004", "present": True},
    {"level": "Declared", "rule": "HC-R005", "present": True},
    {"level": "Declared", "rule": "HC-OR001", "present": True},
    {"level": "Declared", "rule": "HC-OR003", "present": True},
    {"level": "Declared", "rule": "HC-REF001", "present": True},
    {"level": "Declared", "rule": "HC-REF002", "present": True},
    {"level": "Declared", "rule": "HC-REF003", "present": True},
    {"level": "Declared", "rule": "HC-REF004", "present": True},
    {"level": "Declared", "rule": "HC-REF005", "present": True},
    {"level": "Declared", "rule": "HC-REF006", "present": True},
    {"level": "Declared", "rule": "HC-REF007", "present": True},
    {"level": "Declared", "rule": "HC-REF008", "present": True},
    {"level": "Declared", "rule": "HC-ST002", "present": True},
    {"level": "Declared", "rule": "HC-HF001", "present": True},
    {"level": "Declared", "rule": "HC-HF002", "present": True},
]

# The cumulative size of each level's enforced set: always_rules (3) plus the sets the
# level and the levels below it add. The exact count pins the slice that accumulates the
# levels, so widening it by one level is caught here even though the member names do not
# change.
_COUNTS = [
    {"level": "Structural", "count": 11},
    {"level": "Boundary", "count": 20},
    {"level": "Typed", "count": 39},
    {"level": "Declared", "count": 58},
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
