"""undeclared_members names the workspace members that carry no `.hd` and no exemption,
sorted (honest-check.hd, spec section 8, HC-REF011). It is the membership decision the
workspace gate membership-check.py calls: a module carrying a package manifest but no
declaration escapes every rule in the declaration tier by being invisible, so this names it.
An exempt module, listed in EXEMPT_FROM_DECLARATION with its reason, is subtracted and never
named.

Pins the contract: a member with no declaration and no exemption is returned; a member that
carries a declaration is not; an exempt member is not, even when it lacks a declaration; and
the result is sorted. A stub returning [] fails the first case, and one returning every
member fails the exemption case, so the probe is not vacuous either way.
"""


def probe_undeclared_members():
    try:
        from honest_check.declared import EXEMPT_FROM_DECLARATION, undeclared_members
    except ImportError as exc:
        return [f"cannot import undeclared_members from honest_check.declared: {exc}"]

    exempt_name = next(iter(EXEMPT_FROM_DECLARATION))

    cases = [
        # A member with no declaration and no exemption is named.
        {"members": ["mod_a", "mod_b", "mod_c"], "declared": ["mod_a", "mod_b"], "want": ["mod_c"]},
        # Every member carries a declaration: nothing is owed.
        {"members": ["mod_a"], "declared": ["mod_a"], "want": []},
        # An exempt member with no declaration is not named; a non-exempt one beside it is.
        {"members": [exempt_name, "mod_x"], "declared": [], "want": ["mod_x"]},
        # The result is sorted, not left in input order.
        {"members": ["mod_z", "mod_a"], "declared": [], "want": ["mod_a", "mod_z"]},
    ]

    bad = []
    for case in cases:
        got = undeclared_members(case["members"], case["declared"])
        if got != case["want"]:
            bad.append(
                f"undeclared_members({case['members']!r}, {case['declared']!r}) -> {got!r}, "
                f"expected {case['want']!r}"
            )
    return bad
