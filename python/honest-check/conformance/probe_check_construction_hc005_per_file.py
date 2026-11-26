# scenario: check_construction leaves HC005 to the per-file rule group
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction leaves HC005 to the per-file rule group
"""An undeclared binding key is checked outside the construction phase."""

_SOURCE = b"""from honest_type import binding, classify, vocabulary

cards = vocabulary({'resource': {'users'}})
slots = binding({'resource': 'thing', 'stray': 'slot'})
classify('users', cards, bind=slots)
"""


def probe_check_construction_hc005_per_file():
    """Construction checking leaves HC005 to the per-file rules."""
    from honest_check import build_context, check_construction

    context = build_context(source=_SOURCE, path="hc005.py", rule_config={})
    findings = check_construction(ctx=context)
    hc005 = [finding for finding in findings if finding["rule_id"] == "HC005"]
    if hc005:
        return [f"check_construction returned {hc005!r}, expected no HC005 finding"]
    return []
