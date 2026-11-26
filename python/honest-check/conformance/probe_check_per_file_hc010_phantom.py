# scenario: check_per_file reports an emitted type neither produced nor accepted without a companion declaration
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file reports an emitted type neither produced nor accepted without a companion declaration
"""A declared emission absent from the accepted and produced types is an HC010 warning."""

_SOURCE = b"""from honest_type import binding, link, vocabulary

inp = vocabulary({'in_t': {'a'}})
outp = vocabulary({'out_t': {'b'}})
slots = binding({'in_t': 'in_slot', 'out_t': 'out_slot'})

@link(accepts=inp, emits=outp, bind=slots)
def step(manifest):
    return manifest
"""
_EXPECTED = ('warning',)


def probe_check_per_file_hc010_phantom():
    """A declared emission absent from the accepted and produced types is an HC010 warning."""
    from honest_check import build_context, check_per_file

    ctx = build_context(source=_SOURCE, path="hc010.py", rule_config={})
    findings = check_per_file(ctx=ctx)
    severities = tuple(
        finding["severity"] for finding in findings if finding["rule_id"] == "HC010"
    )
    if severities != _EXPECTED:
        return [f"check_per_file HC010 severities: {severities!r}, expected {_EXPECTED!r}"]
    return []
