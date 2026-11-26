# scenario: check_per_file warns for an unknown explicit binding key
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file warns for an unknown explicit binding key
"""Check that the per-file group warns for an unknown explicit binding key."""

_SOURCE = b"""from honest_type import binding, classify, vocabulary

cards = vocabulary({'resource': {'users'}})
slots = binding({'resource': 'thing', 'stray': 'slot'})
classify(['users'], cards, bind=slots)
"""


def probe_check_per_file_hc005_unknown():
    """Check the HC005 result against a real Python source file."""
    from honest_check import build_context, check_per_file

    context = build_context(source=_SOURCE, path="hc005.py", rule_config={})
    findings = check_per_file(ctx=context)
    hc005 = [finding for finding in findings if finding["rule_id"] == "HC005"]
    actual = [(finding["severity"], "stray" in finding["message"]) for finding in hc005]
    expected = [("warning", True)]
    if actual != expected:
        return [f"check_per_file HC005 findings: {hc005!r}, expected one warning naming 'stray'"]
    return []
