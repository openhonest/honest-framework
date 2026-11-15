"""Conformance probe for enforced_rules_of (honest-check).

Scenario (specs/features/honest-check.feature, Scenario: enforced_rules_of):
enforced_rules_of returns every HC rule enforced at the given adoption level
under the cumulative section 9.4 membership: always_rules at every level, plus
structural_rules at Structural, plus boundary_rules at Boundary, plus
typed_rules at Typed, plus declared_rules at Declared (the whole 58-rule
AdoptionRule set). Its length is the enforced_count the adoption line prints.

The four cumulative level sets and the always-on three are declared as data in
honest-check.hd (sets structural_rules, boundary_rules, typed_rules,
declared_rules, always_rules). Each case below pins the exact membership the
scenario fixes for one level, built up cumulatively from those sets.

The return type is list<AdoptionRule>, but neither the scenario nor the .hd note
fixes an order, so the probe compares membership (as a set) and checks the length
to catch duplicates. Ordering is a gap owned by the feature/hd.
"""


# The five section-9.4 sets, transcribed from honest-check.hd (lines 189-193).
_ALWAYS = {"HC-SYN", "HC-SUP001", "HC-SUP002"}
_STRUCTURAL = {"HC-P001", "HC-P003", "HC-P007", "HC-P011", "HC-P016", "HC-P015", "HC-P019", "HC-P020"}
_BOUNDARY = {
    "HC-P002", "HC-P004", "HC-P005", "HC-P006", "HC-P010",
    "HC-P013", "HC-ST001", "HC-A001", "HC-A002",
}
_TYPED = {
    "HC001", "HC002", "HC003", "HC004", "HC005", "HC006", "HC007",
    "HC008", "HC009", "HC010", "HC011", "HC-SM01", "HC-SM02",
    "HC-SM03", "HC-SM04", "HC-SM05", "HC-P014", "HC-P017", "HC-P018",
}
_DECLARED = {
    "HC-R001", "HC-R002", "HC-R003", "HC-R004", "HC-R005", "HC-OR001",
    "HC-OR003", "HC-REF001", "HC-REF002", "HC-REF003", "HC-REF004",
    "HC-REF005", "HC-REF006", "HC-REF007", "HC-REF008", "HC-REF012", "HC-ST002",
    "HC-HF001", "HC-HF002",
}

# Cumulative membership per level, written out as literals the scenario fixes.
_STRUCTURAL_MEMBERS = _ALWAYS | _STRUCTURAL                       # 11
_BOUNDARY_MEMBERS = _STRUCTURAL_MEMBERS | _BOUNDARY               # 20
_TYPED_MEMBERS = _BOUNDARY_MEMBERS | _TYPED                       # 39
_DECLARED_MEMBERS = _TYPED_MEMBERS | _DECLARED                    # 58

_CASES = [
    # Structural: always_rules plus the five structural rules.
    {"level": "Structural", "expect": _STRUCTURAL_MEMBERS},
    # Boundary: Structural plus the nine boundary rules.
    {"level": "Boundary", "expect": _BOUNDARY_MEMBERS},
    # Typed: Boundary plus the eighteen typed rules.
    {"level": "Typed", "expect": _TYPED_MEMBERS},
    # Declared: the whole 58-rule set; a codebase that declares nothing is held here.
    {"level": "Declared", "expect": _DECLARED_MEMBERS},
]


def probe_enforced_rules_of():
    """enforced_rules_of returns the cumulative section 9.4 rule set for each adoption level."""
    try:
        from honest_check import enforced_rules_of
    except ImportError as exc:
        return [f"cannot import enforced_rules_of: {exc}"]

    bad = []
    for case in _CASES:
        got = enforced_rules_of(level=case["level"])
        expect = case["expect"]
        got_set = set(got)
        if got_set != expect:
            missing = sorted(expect - got_set)
            extra = sorted(got_set - expect)
            bad.append(
                f"enforced_rules_of(level={case['level']!r}) membership wrong: "
                f"missing {missing}, unexpected {extra}"
            )
        elif len(got) != len(expect):
            bad.append(
                f"enforced_rules_of(level={case['level']!r}) returned {len(got)} items "
                f"for {len(expect)} distinct rules — duplicates present"
            )
    return bad
