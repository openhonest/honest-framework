# scenario: check_construction leaves HC010 to the per-file rule group
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction leaves HC010 to the per-file rule group
"""Construction checking leaves HC010 to the per-file rules."""

_SOURCE = b"""from honest_type import binding, link, vocabulary

inp = vocabulary({'in_t': {'a'}})
outp = vocabulary({'out_t': {'b'}})
slots = binding({'in_t': 'in_slot', 'out_t': 'out_slot'})

@link(accepts=inp, emits=outp, bind=slots)
def step(manifest):
    return manifest
"""
_EXPECTED = ()


def probe_check_construction_hc010_per_file():
    """Construction checking leaves HC010 to the per-file rules."""
    from honest_check import build_context, check_construction

    ctx = build_context(source=_SOURCE, path="hc010.py", rule_config={})
    findings = check_construction(ctx=ctx)
    severities = tuple(
        finding["severity"] for finding in findings if finding["rule_id"] == "HC010"
    )
    if severities != _EXPECTED:
        return [f"check_construction HC010 severities: {severities!r}, expected {_EXPECTED!r}"]
    return []
