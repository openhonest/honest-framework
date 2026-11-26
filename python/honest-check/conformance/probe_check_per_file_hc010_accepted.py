# scenario: check_per_file allows an emitted type accepted by the link
# inherits: hd=python/honest-check/honest-check.hd::check_per_file -> feature=specs/features/honest-check.feature::check_per_file allows an emitted type accepted by the link
"""A declared and accepted emission yields no HC010 finding."""

_SOURCE = b"""from honest_type import binding, link, vocabulary

inp = vocabulary({'in_t': {'a'}})
outp = vocabulary({'out_t': {'b'}})
slots = binding({'in_t': 'in_slot', 'out_t': 'out_slot'})

@link(accepts=inp, emits=inp, bind=slots)
def step(manifest):
    return manifest
"""
_EXPECTED = ()


def probe_check_per_file_hc010_accepted():
    """A declared and accepted emission yields no HC010 finding."""
    from honest_check import build_context, check_per_file

    ctx = build_context(source=_SOURCE, path="hc010.py", rule_config={})
    findings = check_per_file(ctx=ctx)
    severities = tuple(
        finding["severity"] for finding in findings if finding["rule_id"] == "HC010"
    )
    if severities != _EXPECTED:
        return [f"check_per_file HC010 severities: {severities!r}, expected {_EXPECTED!r}"]
    return []
