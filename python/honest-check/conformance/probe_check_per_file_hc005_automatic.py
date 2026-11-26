# scenario: check_per_file skips automatic binding
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file skips automatic binding
"""Check that the per-file group skips automatic binding."""

_SOURCE = b"""from honest_type import classify, vocabulary

cards = vocabulary({'resource': {'users'}})
classify(['users'], cards)
"""


def probe_check_per_file_hc005_automatic():
    """Check the HC005 result against a real Python source file."""
    from honest_check import build_context, check_per_file

    context = build_context(source=_SOURCE, path="hc005.py", rule_config={})
    findings = check_per_file(ctx=context)
    hc005 = [finding for finding in findings if finding["rule_id"] == "HC005"]
    if hc005:
        return [f"check_per_file returned {hc005!r}, expected no HC005 finding"]
    return []
